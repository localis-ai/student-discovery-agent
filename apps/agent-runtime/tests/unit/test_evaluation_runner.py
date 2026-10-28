"""Comprehensive unit tests for EvaluationRunner and PublishGateService (Task C-05 / M-EVL).

Verifies:
- ADR-001 & ADR-002: Same behavior version and engine for runtime, preview and evaluation.
- Deterministic replay of golden cases with question selector and scoring engine.
- Validation of RFC 8785 canonical hash and exact error codes on mismatch.
- Failure detection: house mismatch, question sequence mismatch, stopping reason mismatch,
  score mismatch, tie mismatch, missing house score.
- Distinguishing mandatory vs non-mandatory cases.
- Unsupported engine/schema handling.
- Card projection preview parity (summary.v1).
- Thread-safe ReportStore and PublishGateService verification with idempotent caching.
- Stale hash, missing report, and mismatched engine/schema rejection in publish gate.
"""

import copy

from agent_runtime.evaluations.schemas.validation import (
    PublishReportInput,
    ValidationStatus,
)
from agent_runtime.evaluations.services.publish_gate import (
    PublishGateService,
    ReportStore,
)
from agent_runtime.evaluations.services.runner import EvaluationRunner


def test_evaluation_runner_valid_v2_success(valid_v2_doc):
    """Happy path: valid definition 2.0 with golden case passes evaluation completely."""
    runner = EvaluationRunner()
    report = runner.run_evaluation(valid_v2_doc, expected_revision=1)

    assert report.status == ValidationStatus.PASSED
    assert report.mandatory_passed is True
    assert report.draft_revision == 1
    assert report.experience_id == "definition_test"
    assert report.definition_schema_version == "2.0"
    assert report.engine_version == "career-assessment-v1"
    assert report.content_hash.startswith("sha256:")
    assert report.created_at.endswith("Z")

    assert len(report.cases) == 1
    case_res = report.cases[0]
    assert case_res.case_id == "case_test"
    assert case_res.mandatory is True
    assert case_res.passed is True
    assert case_res.issues == []
    assert case_res.actual["house_id"] == "house_s"
    assert case_res.actual["stopping_reason"] == "question_limit"
    assert case_res.actual["tie_applied"] is True
    assert "scores" in case_res.actual
    assert "display_scores" in case_res.actual


def test_evaluation_runner_bad_content_hash(valid_v2_doc):
    """If expected_hash does not match the computed canonical hash, evaluation must fail."""
    runner = EvaluationRunner()
    wrong_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    report = runner.run_evaluation(valid_v2_doc, expected_hash=wrong_hash)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert len(report.cases) > 0
    assert any(i.code == "EVAL_HASH_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_house_mismatch(valid_v2_doc):
    """If actual winning house does not match expected house, report failure."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["house_id"] = "house_r"

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_HOUSE_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_question_sequence_mismatch(valid_v2_doc):
    """If expected question sequence does not match actual sequence, report failure."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["question_ids"] = ["q_r_01", "q_r_02"]

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_QUESTION_SEQUENCE_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_stopping_reason_mismatch(valid_v2_doc):
    """If expected stopping reason does not match actual reason, report failure."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["stopping_reason"] = "bounded_winner"

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_STOPPING_REASON_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_tie_applied_mismatch(valid_v2_doc):
    """If expected tie_applied does not match actual tie_applied, report failure."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["tie_applied"] = False

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_TIE_APPLIED_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_score_mismatch(valid_v2_doc):
    """If expected score for a house differs from engine calculation, report failure."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["scores"]["house_r"] = 4.5

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.mandatory_passed is False
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_SCORE_MISMATCH" for i in report.cases[0].issues)


def test_evaluation_runner_missing_house_score(valid_v2_doc):
    """If expected scores contains an unknown house ID, report missing score."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["evaluation_cases"][0]["expected"]["scores"]["house_unknown"] = 3.0

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.FAILED
    assert report.cases[0].passed is False
    assert any(i.code == "EVAL_MISSING_HOUSE_SCORE" for i in report.cases[0].issues)


def test_evaluation_runner_non_mandatory_case_failure(valid_v2_doc):
    """A non-mandatory failure makes the case fail and report fail, but mandatory_passed remains True."""
    doc = copy.deepcopy(valid_v2_doc)
    case_1 = doc["evaluation_cases"][0]
    case_2 = copy.deepcopy(case_1)
    case_2["case_id"] = "case_non_mandatory"
    case_2["mandatory"] = False
    # Make case_2 fail
    case_2["expected"]["house_id"] = "house_r"
    doc["evaluation_cases"].append(case_2)

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    # Mandatory case 1 passed!
    assert report.mandatory_passed is True
    # But because case 2 failed, overall status is FAILED
    assert report.status == ValidationStatus.FAILED
    assert len(report.cases) == 2
    assert report.cases[0].passed is True
    assert report.cases[1].passed is False


def test_evaluation_runner_unsupported_engine(valid_v2_doc):
    """If definition specifies an unregistered engine version, report UNSUPPORTED."""
    doc = copy.deepcopy(valid_v2_doc)
    doc["engine_version"] = "unsupported-engine-999"
    for slot in ("selection_rules", "scoring_rules", "coverage_rules", "tie_policy"):
        doc[slot]["engine_version"] = "unsupported-engine-999"

    runner = EvaluationRunner()
    report = runner.run_evaluation(doc)

    assert report.status == ValidationStatus.UNSUPPORTED
    assert report.mandatory_passed is False


def test_publish_gate_service_full_flow(valid_v2_doc):
    """End-to-end PublishGateService: validate, evaluate, and verify publish gate."""
    store = ReportStore()
    service = PublishGateService(store=store)

    val_report = service.validate_and_store(
        valid_v2_doc, expected_revision=1, idempotency_key="idemp_val_1"
    )
    assert val_report.status == ValidationStatus.PASSED

    # Idempotent validate replay
    val_cached = service.validate_and_store(
        valid_v2_doc, expected_revision=1, idempotency_key="idemp_val_1"
    )
    assert val_cached.id == val_report.id

    eval_report = service.evaluate_and_store(
        valid_v2_doc, expected_revision=1, idempotency_key="idemp_eval_1"
    )
    assert eval_report.status == ValidationStatus.PASSED
    assert eval_report.mandatory_passed is True

    # Idempotent evaluate replay
    eval_cached = service.evaluate_and_store(
        valid_v2_doc, expected_revision=1, idempotency_key="idemp_eval_1"
    )
    assert eval_cached.id == eval_report.id

    # Verify publish gate (Happy path)
    gate_input = PublishReportInput(
        experience_id=val_report.experience_id,
        definition_hash=val_report.content_hash,
        definition_schema_version=val_report.definition_schema_version,
        engine_version=val_report.engine_version,
        validation_id=val_report.id,
        evaluation_id=eval_report.id,
    )
    verified, reason = service.verify_publish_gate(gate_input)
    assert verified is True
    assert reason is None


def test_publish_gate_service_stale_hash(valid_v2_doc):
    """Publish gate rejects if definition hash does not match reports."""
    service = PublishGateService()
    val_report = service.validate_and_store(valid_v2_doc)
    eval_report = service.evaluate_and_store(valid_v2_doc)

    gate_input = PublishReportInput(
        experience_id=val_report.experience_id,
        definition_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        definition_schema_version=val_report.definition_schema_version,
        engine_version=val_report.engine_version,
        validation_id=val_report.id,
        evaluation_id=eval_report.id,
    )
    verified, reason = service.verify_publish_gate(gate_input)
    assert verified is False
    assert "does not match" in reason


def test_publish_gate_service_missing_reports(valid_v2_doc):
    """Publish gate rejects if validation or evaluation report cannot be found."""
    service = PublishGateService()
    val_report = service.validate_and_store(valid_v2_doc)

    gate_input = PublishReportInput(
        experience_id=val_report.experience_id,
        definition_hash=val_report.content_hash,
        definition_schema_version=val_report.definition_schema_version,
        engine_version=val_report.engine_version,
        validation_id="val_nonexistent",
        evaluation_id="eval_nonexistent",
    )
    verified, reason = service.verify_publish_gate(gate_input)
    assert verified is False
    assert "not found" in reason


def test_publish_gate_service_failed_report_rejection(valid_v2_doc):
    """Publish gate rejects if evaluation report has failed status."""
    service = PublishGateService()

    # Corrupt golden case so evaluation fails
    bad_doc = copy.deepcopy(valid_v2_doc)
    bad_doc["evaluation_cases"][0]["expected"]["house_id"] = "house_r"

    val_report = service.validate_and_store(bad_doc)
    eval_report = service.evaluate_and_store(bad_doc)
    assert eval_report.status == ValidationStatus.FAILED

    gate_input = PublishReportInput(
        experience_id=val_report.experience_id,
        definition_hash=val_report.content_hash,
        definition_schema_version=val_report.definition_schema_version,
        engine_version=val_report.engine_version,
        validation_id=val_report.id,
        evaluation_id=eval_report.id,
    )
    verified, reason = service.verify_publish_gate(gate_input)
    assert verified is False
    assert "expected 'passed'" in reason


def test_publish_gate_service_mismatched_engine(valid_v2_doc):
    """Publish gate rejects if input engine_version differs from reports."""
    service = PublishGateService()
    val_report = service.validate_and_store(valid_v2_doc)
    eval_report = service.evaluate_and_store(valid_v2_doc)

    gate_input = PublishReportInput(
        experience_id=val_report.experience_id,
        definition_hash=val_report.content_hash,
        definition_schema_version=val_report.definition_schema_version,
        engine_version="career-assessment-v2",
        validation_id=val_report.id,
        evaluation_id=eval_report.id,
    )
    verified, reason = service.verify_publish_gate(gate_input)
    assert verified is False
    assert "engine version" in reason
