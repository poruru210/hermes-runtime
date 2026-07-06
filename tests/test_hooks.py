from advisor_gate.config import AdvisorGateConfig
from advisor_gate.event_hooks import on_post_tool_call, on_subagent_start, on_subagent_stop
from advisor_gate.final_gate import (
    on_final_delivery_gate,
    on_pre_verify,
    on_transform_llm_output,
)
from advisor_gate.pre_tool_gate import on_pre_tool_call
from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    AdvisorVerdict,
    Finding,
    FindingCategory,
    Severity,
    resolution_gate_from_dict,
)
from advisor_gate.store import ReceiptStore


def _append_pass_phase(store: ReceiptStore, session_id: str, phase: AdvisorPhase) -> None:
    store.append_result(
        session_id=session_id,
        result=AdvisorResult(phase=phase, verdict=AdvisorVerdict.PASS),
        source="test",
    )


def _append_pass_phase_for_turn(
    store: ReceiptStore,
    session_id: str,
    phase: AdvisorPhase,
    turn_id: str,
) -> None:
    store.append_result(
        session_id=session_id,
        result=AdvisorResult(phase=phase, verdict=AdvisorVerdict.PASS),
        source="test",
        extra={"call_context": {"turn_id": turn_id}},
    )


def _append_pass_final(store: ReceiptStore, session_id: str, final_draft: str = "done") -> None:
    store.append_result(
        session_id=session_id,
        result=AdvisorResult(phase=AdvisorPhase.A3_FINAL, verdict=AdvisorVerdict.PASS),
        source="test",
        extra={
            "packet": {
                "actions_taken": [],
                "tests_or_checks": [],
                "known_unresolved": [],
                "final_answer_draft": final_draft,
                "flow_summary": "tested",
            }
        },
    )


def test_subagent_stop_writes_receipt(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_subagent_stop(
        store,
        parent_session_id="parent",
        child_role="leaf",
        child_status="completed",
        child_summary="done",
        duration_ms=10,
    )

    entry = store.read_all()[0]
    assert entry["source"] == "subagent_stop"
    assert entry["session_id"] == "parent"
    assert entry["extra"]["child_role"] == "leaf"


def test_missing_final_transforms_output(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    transformed = on_transform_llm_output(
        store,
        AdvisorGateConfig(),
        response_text="done",
        session_id="s1",
    )

    assert transformed is not None
    assert "A3_FINAL audit receipt is missing" in transformed


def test_subagent_final_gate_is_skipped_by_default(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_subagent_start(
        store,
        parent_session_id="parent",
        child_session_id="child",
        child_role="leaf",
    )

    assert store.is_child_session("child") is True
    assert (
        on_transform_llm_output(
            store,
            AdvisorGateConfig(),
            response_text="done",
            session_id="child",
        )
        is None
    )
    assert (
        on_pre_verify(
            store,
            AdvisorGateConfig(),
            session_id="child",
            final_response="done",
            changed_paths=["x.py"],
        )
        is None
    )


def test_parent_final_gate_defers_while_subagent_is_active(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_subagent_start(
        store,
        parent_session_id="parent",
        child_session_id="child",
        child_role="leaf",
    )

    assert store.active_child_sessions("parent") == ("child",)
    transformed = on_transform_llm_output(
        store,
        AdvisorGateConfig(),
        response_text="delegation dispatched",
        session_id="parent",
    )
    assert transformed is not None
    assert "subagent work is still active" in transformed

    on_subagent_stop(
        store,
        parent_session_id="parent",
        child_session_id="child",
        child_status="completed",
        child_summary="done",
    )

    transformed = on_transform_llm_output(
        store,
        AdvisorGateConfig(),
        response_text="done",
        session_id="parent",
    )
    assert transformed is not None
    assert "A3_FINAL audit receipt is missing" in transformed


def test_pre_tool_call_allows_advisor_tools_without_a1(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="advisor_audit",
            session_id="s1",
        )
        is None
    )


def test_pre_tool_call_blocks_action_tool_until_a1_passes(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    response = on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="terminal",
        session_id="s1",
        args={"command": "touch x"},
    )

    assert response is not None
    assert response["action"] == "block"
    assert "A1_PLAN" in response["message"]
    entry = store.read_all()[0]
    assert entry["source"] == "pre_tool_call"
    assert entry["event"] == "blocked_tool_call"


def test_pre_tool_call_allows_action_tool_after_a1_passes(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_phase(store, "s1", AdvisorPhase.A1_PLAN)

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="terminal",
            session_id="s1",
        )
        is None
    )


def test_pre_tool_call_rejects_a1_from_previous_turn(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_phase_for_turn(store, "s1", AdvisorPhase.A1_PLAN, "turn-old")

    response = on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="terminal",
        session_id="s1",
        turn_id="turn-new",
    )

    assert response is not None
    assert response["action"] == "block"
    assert "this turn" in response["message"]


def test_pre_tool_call_allows_a1_from_same_turn(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_phase_for_turn(store, "s1", AdvisorPhase.A1_PLAN, "turn-1")

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="terminal",
            session_id="s1",
            turn_id="turn-1",
        )
        is None
    )


def test_pre_tool_call_blocks_delegation_until_a2_passes(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_phase(store, "s1", AdvisorPhase.A1_PLAN)

    response = on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="delegate_task",
        session_id="s1",
    )

    assert response is not None
    assert response["action"] == "block"
    assert "A2_DELEGATION" in response["message"]


def test_pre_tool_call_allows_delegation_after_a1_and_a2_pass(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_phase(store, "s1", AdvisorPhase.A1_PLAN)
    _append_pass_phase(store, "s1", AdvisorPhase.A2_DELEGATION)

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="delegate_task",
            session_id="s1",
        )
        is None
    )


def test_pre_tool_call_blocks_unclassified_tool_by_default(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    response = on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="dangerous_new_tool",
        session_id="s1",
    )

    assert response is not None
    assert response["action"] == "block"
    assert "A1_PLAN" in response["message"]


def test_prefix_like_mutating_tool_is_not_exempt_by_default(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    response = on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="read_and_delete",
        session_id="s1",
    )

    assert response is not None
    assert response["action"] == "block"


def test_pre_tool_call_ignores_non_action_tool_by_default(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="read_file",
            session_id="s1",
        )
        is None
    )


def test_pre_tool_call_allows_exact_exempt_tool(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    assert (
        on_pre_tool_call(
            store,
            AdvisorGateConfig(),
            tool_name="read_file",
            session_id="s1",
        )
        is None
    )


def test_final_delivery_gate_requests_exception_audit_after_failed_tool(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_post_tool_call(
        store,
        session_id="s1",
        tool_name="terminal",
        status="failed",
        error_type="runtime_error",
        result='{"error": "boom"}',
    )

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="done",
        session_id="s1",
    )

    assert response is not None
    assert response["action"] == "continue"
    assert "A3_EXCEPTION" in response["message"]


def test_final_delivery_gate_returns_to_final_gate_after_exception_passes(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_post_tool_call(
        store,
        session_id="s1",
        tool_name="terminal",
        status="failed",
        error_type="runtime_error",
        result='{"error": "boom"}',
    )
    _append_pass_phase(store, "s1", AdvisorPhase.A3_EXCEPTION)

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="done",
        session_id="s1",
    )

    assert response is not None
    assert "FinalPayload" in response["message"]
    assert "A3_EXCEPTION" not in response["message"]


def test_final_delivery_gate_reaudits_final_after_exception_audit(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "done")
    on_post_tool_call(
        store,
        session_id="s1",
        tool_name="terminal",
        status="failed",
        error_type="runtime_error",
        result='{"error": "boom"}',
    )
    _append_pass_phase(store, "s1", AdvisorPhase.A3_EXCEPTION)

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="done",
        session_id="s1",
    )

    assert response is not None
    assert "A3_FINAL" in response["message"]
    assert "latest tool/subagent/exception event" in response["message"]


def test_plugin_block_does_not_require_exception_audit(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_post_tool_call(
        store,
        session_id="s1",
        tool_name="terminal",
        status="blocked",
        error_type="plugin_block",
        result='{"error": "Advisor Gate blocked the action"}',
    )

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="done",
        session_id="s1",
    )

    assert response is not None
    assert "FinalPayload" in response["message"]
    assert "A3_EXCEPTION" not in response["message"]


def test_pass_final_does_not_transform_output(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "done")

    assert (
        on_transform_llm_output(
            store,
            AdvisorGateConfig(require_resolution_gate=False),
            response_text="done",
            session_id="s1",
        )
        is None
    )


def test_pass_final_still_requires_resolution_gate_by_default(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "done")

    transformed = on_transform_llm_output(
        store,
        AdvisorGateConfig(),
        response_text="done",
        session_id="s1",
    )
    assert transformed is not None
    assert "resolution gate is missing" in transformed


def test_final_delivery_gate_requests_a3_final_when_missing(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="draft",
        session_id="s1",
        changed_paths=["advisor_gate/final_gate.py"],
    )

    assert response is not None
    assert response["action"] == "continue"
    assert "FinalPayload" in response["message"]


def test_final_delivery_gate_requests_resolution_gate_after_pass(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "draft")

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="draft",
        session_id="s1",
    )

    assert response is not None
    assert "advisor_resolution_gate" in response["message"]


def test_pre_verify_requests_resolution_gate_after_pass(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "draft")

    response = on_pre_verify(
        store,
        AdvisorGateConfig(),
        session_id="s1",
        final_response="draft",
    )

    assert response is not None
    assert response["action"] == "continue"
    assert "advisor_resolution_gate" in response["message"]


def test_final_delivery_gate_reaudits_when_final_draft_changed(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "old draft")

    response = on_final_delivery_gate(
        store,
        AdvisorGateConfig(),
        final_response="new draft",
        session_id="s1",
    )

    assert response is not None
    assert "different final_answer_draft" in response["message"]


def test_final_delivery_gate_allows_after_pass_and_resolution_gate(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    _append_pass_final(store, "s1", "draft")
    store.append_resolution_gate(
        session_id="s1",
        gate=resolution_gate_from_dict(
            {
                "commander_decision": "continue",
                "reason": "No open findings.",
                "open_findings": [],
                "resolutions": [],
            }
        ),
        source="test",
    )

    assert (
        on_final_delivery_gate(
            store,
            AdvisorGateConfig(),
            final_response="draft",
            session_id="s1",
        )
        is None
    )


def test_block_final_transforms_output(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    store.append_result(
        session_id="s1",
        result=AdvisorResult(
            phase=AdvisorPhase.A3_FINAL,
            verdict=AdvisorVerdict.BLOCK,
            findings=(
                Finding(
                    finding_id="F-001",
                    severity=Severity.HIGH,
                    category=FindingCategory.SAFETY,
                    message="Unsafe final claim.",
                    recommended_action="Remove the claim.",
                    acceptance_check="Final draft no longer contains it.",
                ),
            ),
        ),
        source="test",
    )

    transformed = on_transform_llm_output(
        store,
        AdvisorGateConfig(),
        response_text="done",
        session_id="s1",
    )
    assert transformed is not None
    assert "BLOCK" in transformed


def test_pre_verify_requests_final_audit_when_missing(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    response = on_pre_verify(
        store,
        AdvisorGateConfig(),
        session_id="s1",
        final_response="done",
            changed_paths=["advisor_gate/final_gate.py"],
    )

    assert response is not None
    assert response["action"] == "continue"
    assert "advisor_audit" in response["message"]


def test_post_tool_call_redacts_and_truncates(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_post_tool_call(
        store,
        session_id="s1",
        tool_name="terminal",
        args={"api_key": "secret", "command": "echo ok"},
        result="x" * 2500,
        duration_ms=1,
    )

    entry = store.read_all()[0]
    assert entry["extra"]["args"]["api_key"] == "[REDACTED]"
    assert entry["extra"]["truncated"] is True
    assert len(entry["extra"]["result_preview"]) == 2000
