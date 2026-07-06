import json
from types import SimpleNamespace

from advisor_gate.audit_handlers import advisor_audit_handler
from advisor_gate.config import AdvisorGateConfig
from advisor_gate.event_hooks import on_post_tool_call
from advisor_gate.final_gate import on_final_delivery_gate
from advisor_gate.pre_tool_gate import on_pre_tool_call
from advisor_gate.resolution_handlers import advisor_resolution_gate_handler
from advisor_gate.store import ReceiptStore


class PassLlm:
    def __init__(self):
        self.calls = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        prompt_packet = json.loads(kwargs["input"][0]["text"])
        parsed = {
            "phase": prompt_packet["phase"],
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
            "diagnostics": [],
            "unavailable_reason": "",
            "final_improvement": "",
        }
        return SimpleNamespace(parsed=parsed, text=json.dumps(parsed))


def _plan_packet():
    return {
        "user_message": "Verify the Commander, Kanban Worker, Advisor flow.",
        "commander_interpretation": "Use Hermes Kanban task evidence; do not modify Hermes core.",
        "task_plan": [
            {"step": "Run A1 plan audit."},
            {"step": "Run A2 Kanban assignment audit."},
            {"step": "Create a Kanban task for a Worker profile."},
            {"step": "Capture Worker kanban_show and kanban_complete evidence."},
            {"step": "Handle one tool exception and final audit."},
        ],
        "coverage_table": [
            {"requirement": "Commander plan", "coverage": "A1_PLAN receipt"},
            {"requirement": "Worker task", "coverage": "Kanban task assignment"},
            {"requirement": "Advisor final gate", "coverage": "A3_FINAL and resolution"},
        ],
        "risk_level": "medium",
        "constraints": ["No Hermes core modification."],
        "source_evidence": [{"source": "official plugin hooks"}],
        "known_unresolved": [],
    }


def _assignment_packet():
    return {
        "commander_plan": "Create one narrow Kanban task for a Worker profile.",
        "worker_assignments": [
            {
                "worker_id": "kanban-worker-1",
                "child_role": "kanban_worker",
                "kanban_task_id": "planned-task-1",
                "parent_task_id": "root-task-1",
                "assignee": "default",
                "dependencies": [],
                "scope": "Read the assigned Kanban task and return a concise result.",
                "expected_evidence": [
                    {"type": "kanban", "description": "kanban_show read of the assigned task"},
                    {"type": "kanban", "description": "kanban_complete summary and metadata"},
                ],
                "completion_contract": "Worker must finish with kanban_complete or kanban_block.",
            }
        ],
        "empty_result_policy": (
            "Treat empty or missing Kanban completion as unresolved and re-scope."
        ),
        "risk_level": "medium",
        "handoff_expectations": (
            "Kanban completion summary and metadata must be reflected in A3_FINAL."
        ),
        "known_unresolved": [],
    }


def _final_packet(final_draft: str):
    return {
        "actions_taken": [
            {"summary": "A1 plan audit passed."},
            {"summary": "A2 Kanban assignment audit passed."},
            {"summary": "Commander created a Kanban task for the Worker profile."},
            {"summary": "Worker completed the Kanban task with summary and metadata."},
            {"summary": "A3 exception audit passed after a planned failed tool event."},
        ],
        "tests_or_checks": [
            {"command": "plugin end-to-end flow", "status": "passed"},
        ],
        "known_unresolved": [],
        "final_answer_draft": final_draft,
        "flow_summary": "A1 -> A2 -> Kanban task -> Worker completion -> A3_EXCEPTION -> A3_FINAL.",
    }


def _audit(
    *,
    store: ReceiptStore,
    config: AdvisorGateConfig,
    llm: PassLlm,
    session_id: str,
    turn_id: str,
    phase: str,
    packet: dict,
) -> dict:
    args = {"phase": phase, "packet": packet, "session_id": session_id}
    on_pre_tool_call(
        store,
        config,
        tool_name="advisor_audit",
        session_id=session_id,
        args=args,
        turn_id=turn_id,
    )
    raw = advisor_audit_handler(
        args,
        llm=llm,
        store=store,
        config=config,
    )
    return json.loads(raw)


def test_commander_kanban_worker_advisor_flow_records_evidence_and_allows_final(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    config = AdvisorGateConfig()
    llm = PassLlm()
    session_id = "commander-session"
    turn_id = "turn-e2e"
    final_draft = "Commander final answer with Worker evidence and Advisor receipts."

    blocked_before_a1 = on_pre_tool_call(
        store,
        config,
        tool_name="terminal",
        session_id=session_id,
        turn_id=turn_id,
    )
    assert blocked_before_a1 is not None
    assert "A1_PLAN" in blocked_before_a1["message"]

    a1 = _audit(
        store=store,
        config=config,
        llm=llm,
        session_id=session_id,
        turn_id=turn_id,
        phase="A1_PLAN",
        packet=_plan_packet(),
    )
    assert a1["policy_action"] == "continue"
    assert (
        on_pre_tool_call(
            store,
            config,
            tool_name="terminal",
            session_id=session_id,
            turn_id=turn_id,
        )
        is None
    )

    blocked_before_a2 = on_pre_tool_call(
        store,
        config,
        tool_name="kanban_create",
        session_id=session_id,
        turn_id=turn_id,
    )
    assert blocked_before_a2 is not None
    assert "A2_DELEGATION" in blocked_before_a2["message"]

    a2 = _audit(
        store=store,
        config=config,
        llm=llm,
        session_id=session_id,
        turn_id=turn_id,
        phase="A2_DELEGATION",
        packet=_assignment_packet(),
    )
    assert a2["policy_action"] == "continue"
    assert (
        on_pre_tool_call(
            store,
            config,
            tool_name="kanban_create",
            session_id=session_id,
            turn_id=turn_id,
        )
        is None
    )

    on_post_tool_call(
        store,
        session_id=session_id,
        tool_name="kanban_create",
        status="success",
        result='{"task_id": "t-kanban-1", "status": "ready"}',
    )
    on_post_tool_call(
        store,
        session_id=session_id,
        tool_name="kanban_show",
        status="success",
        result='{"task_id": "t-kanban-1", "title": "Worker check"}',
    )
    on_post_tool_call(
        store,
        session_id=session_id,
        tool_name="kanban_complete",
        status="success",
        result='{"task_id": "t-kanban-1", "summary": "Worker completed with evidence"}',
    )

    on_post_tool_call(
        store,
        session_id=session_id,
        tool_name="terminal",
        status="failed",
        error_type="runtime_error",
        result='{"error": "planned validation failure"}',
    )
    exception_gate = on_final_delivery_gate(
        store,
        config,
        session_id=session_id,
        final_response=final_draft,
    )
    assert exception_gate is not None
    assert "A3_EXCEPTION" in exception_gate["message"]

    a3_exception = _audit(
        store=store,
        config=config,
        llm=llm,
        session_id=session_id,
        turn_id=turn_id,
        phase="A3_EXCEPTION",
        packet={"failure": "planned validation failure", "recovery": "recorded"},
    )
    assert a3_exception["policy_action"] == "continue"

    final_gate = on_final_delivery_gate(
        store,
        config,
        session_id=session_id,
        final_response=final_draft,
    )
    assert final_gate is not None
    assert "A3_FINAL" in final_gate["message"]

    a3_final = _audit(
        store=store,
        config=config,
        llm=llm,
        session_id=session_id,
        turn_id=turn_id,
        phase="A3_FINAL",
        packet=_final_packet(final_draft),
    )
    assert a3_final["policy_action"] == "continue"

    prompt_packet = json.loads(llm.calls[-1]["input"][0]["text"])
    actions = prompt_packet["payload"]["actions_taken"]
    assert any("Kanban task" in item["summary"] for item in actions)

    resolution_required = on_final_delivery_gate(
        store,
        config,
        session_id=session_id,
        final_response=final_draft,
    )
    assert resolution_required is not None
    assert "advisor_resolution_gate" in resolution_required["message"]

    resolution = json.loads(
        advisor_resolution_gate_handler(
            {
                "commander_decision": "continue",
                "reason": "All Advisor findings are closed and receipts are present.",
                "open_findings": [],
                "resolutions": [],
                "session_id": session_id,
            },
            store=store,
            config=config,
        )
    )
    assert resolution["policy_action"] == "continue"

    assert (
        on_final_delivery_gate(
            store,
            config,
            session_id=session_id,
            final_response=final_draft,
        )
        is None
    )

    entries = store.read_all()
    phases = [entry.get("phase") for entry in entries]
    assert "A1_PLAN" in phases
    assert "A2_DELEGATION" in phases
    assert "A3_EXCEPTION" in phases
    assert "A3_FINAL" in phases
    assert "RESOLUTION_GATE" in phases
    assert any(entry.get("extra", {}).get("tool_name") == "kanban_create" for entry in entries)
    assert any(entry.get("extra", {}).get("tool_name") == "kanban_complete" for entry in entries)
