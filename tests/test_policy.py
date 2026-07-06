from advisor_gate.policy import PolicyAction, build_gate_message, decide_action
from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    AdvisorVerdict,
    Finding,
    FindingCategory,
    Severity,
)


def test_block_maps_to_stop():
    result = AdvisorResult(phase=AdvisorPhase.A3_FINAL, verdict=AdvisorVerdict.BLOCK)
    assert decide_action(result) is PolicyAction.STOP


def test_changes_required_maps_to_requires_resolution():
    result = AdvisorResult(
        phase=AdvisorPhase.A3_FINAL,
        verdict=AdvisorVerdict.CHANGES_REQUIRED,
        findings=(
            Finding(
                finding_id="F-001",
                severity=Severity.MEDIUM,
                category=FindingCategory.FINAL_QUALITY,
                message="Needs a clearer test report.",
                recommended_action="Add command results.",
                acceptance_check="Final response names checks run.",
            ),
        ),
    )
    assert decide_action(result) is PolicyAction.REQUIRES_RESOLUTION


def test_high_severity_prevents_silent_pass():
    result = AdvisorResult(
        phase=AdvisorPhase.A3_FINAL,
        verdict=AdvisorVerdict.PASS,
        findings=(
            Finding(
                finding_id="F-002",
                severity=Severity.HIGH,
                category=FindingCategory.SAFETY,
                message="High severity issue cannot silently pass.",
                recommended_action="Resolve high severity finding.",
                acceptance_check="No high severity findings remain.",
            ),
        ),
    )
    assert decide_action(result) is PolicyAction.REQUIRES_RESOLUTION


def test_missing_final_gate_message():
    message = build_gate_message(None, missing_final=True)
    assert "A3_FINAL audit receipt is missing" in message
    assert "CHANGES_REQUIRED" in message
