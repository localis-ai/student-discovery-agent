"""Deterministic Evaluation Runner Engine Service (Task C-05 / M-EVL).

Conforms to:
- contracts/openapi/public/experience-validation-api.yaml (EvaluationReport, EvaluationCaseResult)
- ADR-001 & ADR-002: Exact same behavior version and engine for runtime, preview and evaluation.
- Deterministic First: 100% deterministic rule replay (AdaptiveQuestionSelector, ScoringEngine,
  project_summary_from_result).
- RFC 8785 canonical JSON hashing (via ExperienceValidator canonical hashing).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Mapping
from uuid import uuid4

from pydantic import ValidationError

from agent_runtime.evaluations.schemas.experience import (
    AssessmentGoldenCase,
    ExperienceDefinitionDocument,
)
from agent_runtime.evaluations.schemas.validation import (
    EvaluationCaseResult,
    EvaluationReport,
    ValidationIssue,
    ValidationStatus,
)
from agent_runtime.evaluations.services.compatibility import (
    PILOT_ENGINE_REGISTRY,
    CompatibilityChecker,
)
from agent_runtime.evaluations.services.validator import ExperienceValidator

if TYPE_CHECKING:
    from agent_runtime.engine.schemas.scoring import AssessmentScoringResult


class EvaluationRunner:
    """Authoritative evaluation runner using the exact same engine as preview and runtime."""

    def __init__(
        self,
        validator: ExperienceValidator | None = None,
        compatibility: CompatibilityChecker | None = None,
        selector: Any | None = None,
        scorer: Any | None = None,
    ) -> None:
        from agent_runtime.engine.services.scorer import ScoringEngine
        from agent_runtime.engine.services.selector import AdaptiveQuestionSelector

        self._compatibility = compatibility or CompatibilityChecker(PILOT_ENGINE_REGISTRY)
        self._validator = validator or ExperienceValidator(self._compatibility)
        self._selector = selector or AdaptiveQuestionSelector()
        self._scorer = scorer or ScoringEngine()

    def run_evaluation(
        self,
        definition: ExperienceDefinitionDocument | Mapping[str, Any],
        expected_revision: int = 1,
        expected_hash: str | None = None,
        idempotency_key: str | None = None,
        experience_id: str | None = None,
    ) -> EvaluationReport:
        """Run complete golden evaluation cases against the authoritative engine.

        Steps:
        1. Validates structural and rule compatibility using ExperienceValidator.
        2. Computes the canonical RFC 8785 SHA-256 hash.
        3. Replays every AssessmentGoldenCase with the exact same AdaptiveQuestionSelector
           and ScoringEngine as runtime/preview, respecting seed for deterministic order.
        4. Verifies preview/runtime card projection via summary_v1 without side-effects.
        5. Aggregates results into an immutable, typed EvaluationReport.
        """
        raw_dict = (
            definition.model_dump(mode="json")
            if isinstance(definition, ExperienceDefinitionDocument)
            else dict(definition)
        )

        exp_id = experience_id or str(raw_dict.get("definition_id", "exp_default"))

        val_report = self._validator.validate(
            doc_input=raw_dict,
            experience_id=exp_id,
            draft_revision=expected_revision,
        )

        content_hash = val_report.content_hash
        schema_version = str(raw_dict.get("schema_version", "2.0"))
        engine_version = str(raw_dict.get("engine_version", "unknown"))

        hash_mismatch_issue: ValidationIssue | None = None
        if expected_hash and content_hash != expected_hash:
            hash_mismatch_issue = ValidationIssue(
                path="content_hash",
                code="EVAL_HASH_MISMATCH",
                message=f"Provided content_hash '{expected_hash}' does not match computed hash '{content_hash}'.",
                rule_id="EVALUATION_REPORT_INTEGRITY",
            )

        if val_report.status == ValidationStatus.UNSUPPORTED:
            return self._build_report(
                report_id=f"eval_{uuid4().hex[:16]}",
                experience_id=exp_id,
                draft_revision=expected_revision,
                content_hash=content_hash,
                definition_schema_version=schema_version,
                engine_version=engine_version,
                status=ValidationStatus.UNSUPPORTED,
                mandatory_passed=False,
                cases=[],
            )

        try:
            def_doc = (
                definition
                if isinstance(definition, ExperienceDefinitionDocument)
                else ExperienceDefinitionDocument.model_validate(raw_dict)
            )
        except ValidationError as parse_err:
            issues = [
                ValidationIssue(
                    path=f"definition.{'.'.join(str(p) for p in err.get('loc', []))}",
                    code="EVAL_MALFORMED_DEFINITION",
                    message=err.get("msg", "Malformed definition"),
                    rule_id="EVALUATION_DOCUMENT_PARSE",
                )
                for err in parse_err.errors()
            ]
            if hash_mismatch_issue:
                issues.insert(0, hash_mismatch_issue)
            return self._build_report(
                report_id=f"eval_{uuid4().hex[:16]}",
                experience_id=exp_id,
                draft_revision=expected_revision,
                content_hash=content_hash,
                definition_schema_version=schema_version,
                engine_version=engine_version,
                status=ValidationStatus.FAILED,
                mandatory_passed=False,
                cases=[
                    EvaluationCaseResult(
                        case_id="case_parse_error",
                        mandatory=True,
                        passed=False,
                        expected={},
                        actual={},
                        issues=issues,
                    )
                ],
            )

        case_results: list[EvaluationCaseResult] = []
        for golden_case in def_doc.evaluation_cases:
            case_result = self._evaluate_case(golden_case, def_doc, raw_dict)
            case_results.append(case_result)

        if hash_mismatch_issue and case_results:
            case_results[0].issues.insert(0, hash_mismatch_issue)
            case_results[0].passed = False

        mandatory_cases = [c for c in case_results if c.mandatory]
        mandatory_passed = (
            len(mandatory_cases) > 0
            and all(c.passed for c in mandatory_cases)
            and val_report.status == ValidationStatus.PASSED
            and hash_mismatch_issue is None
        )
        all_cases_passed = (
            len(case_results) > 0
            and all(c.passed for c in case_results)
            and val_report.status == ValidationStatus.PASSED
            and hash_mismatch_issue is None
        )

        final_status = (
            ValidationStatus.PASSED if all_cases_passed and mandatory_passed else ValidationStatus.FAILED
        )

        return self._build_report(
            report_id=f"eval_{uuid4().hex[:16]}",
            experience_id=exp_id,
            draft_revision=expected_revision,
            content_hash=content_hash,
            definition_schema_version=def_doc.schema_version,
            engine_version=def_doc.engine_version,
            status=final_status,
            mandatory_passed=mandatory_passed,
            cases=case_results,
        )

    def _evaluate_case(
        self,
        case: AssessmentGoldenCase,
        def_doc: ExperienceDefinitionDocument,
        raw_dict: Mapping[str, Any],
    ) -> EvaluationCaseResult:
        """Evaluate a single golden case against question selector, scoring engine and card projector."""
        from agent_runtime.engine.exceptions import (
            EngineError,
            MissingMappingError,
            UnsupportedDefinitionError,
        )
        from agent_runtime.engine.projection.summary_v1 import project_summary_from_result

        issues: list[ValidationIssue] = []
        case_id = case.case_id
        seed = case.seed
        expected = case.expected

        actual_question_ids: list[str] = []
        actual_primary_house_id: str | None = None
        actual_scores: dict[str, float] = {}
        actual_display_scores: dict[str, int] = {}
        actual_stopping_reason: str | None = None
        actual_tie_applied: bool = False
        actual_holland_code: str | None = None

        ans_payloads = [
            {"question_id": a.question_id, "option_id": a.option_id}
            for a in case.answers
        ]

        try:
            for step_idx in range(len(ans_payloads)):
                prefix = ans_payloads[:step_idx]
                step_res = self._selector.select_next_question(
                    answers=prefix,
                    definition=raw_dict,
                    validate_sequence=False,
                    seed=seed,
                )
                if step_res.next_question_id:
                    actual_question_ids.append(step_res.next_question_id)
                    if step_res.next_question_id != ans_payloads[step_idx]["question_id"]:
                        issues.append(
                            ValidationIssue(
                                path=f"evaluation_cases[{case_id}].answers[{step_idx}].question_id",
                                code="EVAL_UNEXPECTED_QUESTION_IN_SEQUENCE",
                                message=(
                                    f"At step {step_idx + 1}, engine selected question "
                                    f"'{step_res.next_question_id}' but golden answer provided was for "
                                    f"'{ans_payloads[step_idx]['question_id']}'."
                                ),
                                rule_id="EVALUATION_SEQUENCE_INTEGRITY",
                            )
                        )

            final_sel = self._selector.select_next_question(
                answers=ans_payloads,
                definition=raw_dict,
                validate_sequence=False,
                seed=seed,
            )
            if final_sel.stopping_reason:
                actual_stopping_reason = (
                    final_sel.stopping_reason.value
                    if hasattr(final_sel.stopping_reason, "value")
                    else str(final_sel.stopping_reason)
                )
            if final_sel.primary_house_id:
                actual_primary_house_id = final_sel.primary_house_id

        except (EngineError, ValidationError, Exception) as sel_err:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].selector",
                    code="EVAL_SELECTOR_EXECUTION_ERROR",
                    message=f"Adaptive question selector failed on golden case: {sel_err}",
                    rule_id="EVALUATION_ENGINE_REPLAY",
                )
            )

        scoring_res: AssessmentScoringResult | None = None
        try:
            scoring_res = self._scorer.calculate_scores(
                answers=ans_payloads,
                definition=raw_dict,
                seed=seed,
            )
            actual_primary_house_id = scoring_res.primary_house_id
            actual_tie_applied = bool(scoring_res.tie_applied)
            actual_holland_code = scoring_res.holland_code
            if scoring_res.stopping_reason:
                actual_stopping_reason = (
                    scoring_res.stopping_reason.value
                    if hasattr(scoring_res.stopping_reason, "value")
                    else str(scoring_res.stopping_reason)
                )

            actual_scores = {
                house_id: (
                    float(detail.mean.value)
                    if hasattr(detail.mean, "value")
                    else float(detail.mean)
                )
                for house_id, detail in scoring_res.house_scores.items()
            }
            actual_display_scores = {
                house_id: detail.display_score
                for house_id, detail in scoring_res.house_scores.items()
            }

        except (EngineError, ValidationError, Exception) as scr_err:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].scorer",
                    code="EVAL_SCORING_EXECUTION_ERROR",
                    message=f"Scoring engine failed on golden case: {scr_err}",
                    rule_id="EVALUATION_ENGINE_REPLAY",
                )
            )

        if scoring_res is not None:
            try:
                project_summary_from_result(
                    scoring=scoring_res,
                    definition=raw_dict,
                    display_name="Học sinh thử nghiệm",
                    is_demo=def_doc.is_demo,
                    result_id=f"res_eval_{case_id}",
                    result_revision=1,
                    activity_id=f"act_eval_{case_id}",
                )
            except (MissingMappingError, EngineError, UnsupportedDefinitionError, Exception) as prj_err:
                issues.append(
                    ValidationIssue(
                        path=f"evaluation_cases[{case_id}].projection",
                        code="EVAL_CARD_PROJECTION_FAILED",
                        message=f"Preview/Runtime card projection failed: {prj_err}",
                        rule_id="EVALUATION_PREVIEW_PARITY",
                    )
                )

        if expected.house_id != actual_primary_house_id:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].expected.house_id",
                    code="EVAL_HOUSE_MISMATCH",
                    message=(
                        f"Expected primary winning house '{expected.house_id}', "
                        f"but engine produced '{actual_primary_house_id}'."
                    ),
                    rule_id="EVALUATION_OUTCOME_ACCURACY",
                )
            )

        if expected.question_ids is not None and expected.question_ids != actual_question_ids:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].expected.question_ids",
                    code="EVAL_QUESTION_SEQUENCE_MISMATCH",
                    message=(
                        f"Expected question sequence {expected.question_ids}, "
                        f"but actual sequence was {actual_question_ids}."
                    ),
                    rule_id="EVALUATION_OUTCOME_ACCURACY",
                )
            )

        if expected.stopping_reason is not None and expected.stopping_reason != actual_stopping_reason:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].expected.stopping_reason",
                    code="EVAL_STOPPING_REASON_MISMATCH",
                    message=(
                        f"Expected stopping reason '{expected.stopping_reason}', "
                        f"but actual was '{actual_stopping_reason}'."
                    ),
                    rule_id="EVALUATION_OUTCOME_ACCURACY",
                )
            )

        if expected.tie_applied is not None and expected.tie_applied != actual_tie_applied:
            issues.append(
                ValidationIssue(
                    path=f"evaluation_cases[{case_id}].expected.tie_applied",
                    code="EVAL_TIE_APPLIED_MISMATCH",
                    message=(
                        f"Expected tie_applied={expected.tie_applied}, "
                        f"but actual was {actual_tie_applied}."
                    ),
                    rule_id="EVALUATION_OUTCOME_ACCURACY",
                )
            )

        if expected.scores is not None:
            for exp_house, exp_score in expected.scores.items():
                if exp_house not in actual_scores:
                    issues.append(
                        ValidationIssue(
                            path=f"evaluation_cases[{case_id}].expected.scores.{exp_house}",
                            code="EVAL_MISSING_HOUSE_SCORE",
                            message=f"Expected score for house '{exp_house}' was not computed.",
                            rule_id="EVALUATION_OUTCOME_ACCURACY",
                        )
                    )
                else:
                    act_score = actual_scores[exp_house]
                    if abs(act_score - float(exp_score)) > 1e-4:
                        issues.append(
                            ValidationIssue(
                                path=f"evaluation_cases[{case_id}].expected.scores.{exp_house}",
                                code="EVAL_SCORE_MISMATCH",
                                message=(
                                    f"Expected score for house '{exp_house}' to be {exp_score}, "
                                    f"but engine computed {act_score}."
                                ),
                                rule_id="EVALUATION_OUTCOME_ACCURACY",
                            )
                        )

        passed = len(issues) == 0
        expected_dict = {
            k: v for k, v in expected.model_dump().items() if v is not None
        }
        actual_dict = {
            "question_ids": actual_question_ids,
            "house_id": actual_primary_house_id,
            "scores": actual_scores,
            "display_scores": actual_display_scores,
            "stopping_reason": actual_stopping_reason,
            "tie_applied": actual_tie_applied,
            "holland_code": actual_holland_code,
        }

        return EvaluationCaseResult(
            case_id=case_id,
            mandatory=case.mandatory,
            passed=passed,
            expected=expected_dict,
            actual=actual_dict,
            issues=issues,
        )

    def _build_report(
        self,
        *,
        report_id: str,
        experience_id: str,
        draft_revision: int,
        content_hash: str,
        definition_schema_version: str,
        engine_version: str,
        status: ValidationStatus,
        mandatory_passed: bool,
        cases: list[EvaluationCaseResult],
    ) -> EvaluationReport:
        now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return EvaluationReport(
            id=report_id,
            experience_id=experience_id,
            draft_revision=draft_revision,
            content_hash=content_hash,
            definition_schema_version=definition_schema_version,
            engine_version=engine_version,
            status=status,
            mandatory_passed=mandatory_passed,
            cases=cases,
            created_at=now_utc,
        )
