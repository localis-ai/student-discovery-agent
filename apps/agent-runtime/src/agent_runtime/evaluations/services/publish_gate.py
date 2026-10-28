"""Publish Gate & Report Verification Service (Task C-05 / M-EVL).

Conforms to:
- contracts/openapi/public/experience-validation-api.yaml
- ADR-001 §2 (Publish Gate & Immutable Release verification)
- apps/studio-api/src/modules/experiences/experiences.reports.ts (PublishReportInput)
- Thread-safe report storage, idempotent evaluation execution, and strict hash/version pinning.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping

from agent_runtime.evaluations.schemas.experience import ExperienceDefinitionDocument
from agent_runtime.evaluations.schemas.validation import (
    EvaluationReport,
    PublishReportInput,
    ValidationReport,
    ValidationStatus,
)
from agent_runtime.evaluations.services.runner import EvaluationRunner
from agent_runtime.evaluations.services.validator import ExperienceValidator


class ReportStore:
    """Thread-safe report store for validation and evaluation reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._validation_reports: dict[str, ValidationReport] = {}
        self._evaluation_reports: dict[str, EvaluationReport] = {}
        # Secondary index: (experience_id, idempotency_key, content_hash) -> report_id
        self._validation_idemp_index: dict[tuple[str, str, str], str] = {}
        self._evaluation_idemp_index: dict[tuple[str, str, str], str] = {}

    def put_validation(
        self, report: ValidationReport, idempotency_key: str | None = None
    ) -> None:
        with self._lock:
            self._validation_reports[report.id] = report
            if idempotency_key:
                self._validation_idemp_index[
                    (report.experience_id, idempotency_key, report.content_hash)
                ] = report.id

    def get_validation(self, report_id: str) -> ValidationReport | None:
        with self._lock:
            return self._validation_reports.get(report_id)

    def get_validation_by_idempotency(
        self, experience_id: str, idempotency_key: str, content_hash: str
    ) -> ValidationReport | None:
        with self._lock:
            report_id = self._validation_idemp_index.get(
                (experience_id, idempotency_key, content_hash)
            )
            return self._validation_reports.get(report_id) if report_id else None

    def put_evaluation(
        self, report: EvaluationReport, idempotency_key: str | None = None
    ) -> None:
        with self._lock:
            self._evaluation_reports[report.id] = report
            if idempotency_key:
                self._evaluation_idemp_index[
                    (report.experience_id, idempotency_key, report.content_hash)
                ] = report.id

    def get_evaluation(self, report_id: str) -> EvaluationReport | None:
        with self._lock:
            return self._evaluation_reports.get(report_id)

    def get_evaluation_by_idempotency(
        self, experience_id: str, idempotency_key: str, content_hash: str
    ) -> EvaluationReport | None:
        with self._lock:
            report_id = self._evaluation_idemp_index.get(
                (experience_id, idempotency_key, content_hash)
            )
            return self._evaluation_reports.get(report_id) if report_id else None

    def clear(self) -> None:
        """Clear all stored reports (useful for testing)."""
        with self._lock:
            self._validation_reports.clear()
            self._evaluation_reports.clear()
            self._validation_idemp_index.clear()
            self._evaluation_idemp_index.clear()


class PublishGateService:
    """Coordinates validation, evaluation and publish gate verification."""

    def __init__(
        self,
        store: ReportStore | None = None,
        validator: ExperienceValidator | None = None,
        runner: EvaluationRunner | None = None,
    ) -> None:
        self._store = store or ReportStore()
        self._validator = validator or ExperienceValidator()
        self._runner = runner or EvaluationRunner(validator=self._validator)

    @property
    def store(self) -> ReportStore:
        return self._store

    def validate_and_store(
        self,
        definition: ExperienceDefinitionDocument | Mapping[str, Any],
        expected_revision: int = 1,
        idempotency_key: str | None = None,
        experience_id: str | None = None,
    ) -> ValidationReport:
        """Run ExperienceValidator and cache the resulting ValidationReport."""
        raw_dict = (
            definition.model_dump(mode="json")
            if isinstance(definition, ExperienceDefinitionDocument)
            else dict(definition)
        )
        exp_id = experience_id or str(raw_dict.get("definition_id", "exp_default"))

        # Check idempotency replay if possible
        if idempotency_key:
            content_hash = self._validator.canonical_hash(raw_dict)
            cached = self._store.get_validation_by_idempotency(
                exp_id, idempotency_key, content_hash
            )
            if cached:
                return cached

        report = self._validator.validate(
            doc_input=raw_dict,
            experience_id=exp_id,
            draft_revision=expected_revision,
        )
        self._store.put_validation(report, idempotency_key=idempotency_key)
        return report

    def evaluate_and_store(
        self,
        definition: ExperienceDefinitionDocument | Mapping[str, Any],
        expected_revision: int = 1,
        expected_hash: str | None = None,
        idempotency_key: str | None = None,
        experience_id: str | None = None,
    ) -> EvaluationReport:
        """Run EvaluationRunner and cache the resulting EvaluationReport."""
        raw_dict = (
            definition.model_dump(mode="json")
            if isinstance(definition, ExperienceDefinitionDocument)
            else dict(definition)
        )
        exp_id = experience_id or str(raw_dict.get("definition_id", "exp_default"))

        # Check idempotency replay if possible
        if idempotency_key:
            content_hash = self._validator.canonical_hash(raw_dict)
            cached = self._store.get_evaluation_by_idempotency(
                exp_id, idempotency_key, content_hash
            )
            if cached:
                return cached

        report = self._runner.run_evaluation(
            definition=raw_dict,
            expected_revision=expected_revision,
            expected_hash=expected_hash,
            idempotency_key=idempotency_key,
            experience_id=exp_id,
        )
        self._store.put_evaluation(report, idempotency_key=idempotency_key)
        return report

    def verify_publish_gate(
        self, input_data: PublishReportInput | Mapping[str, Any]
    ) -> tuple[bool, str | None]:
        """Verify publish gate conditions matching studio-api PublishReportVerifier.

        Verifies that:
        1. Both validation and evaluation reports exist.
        2. Both reports have status == 'passed' and mandatory_passed == True.
        3. Both reports were evaluated on the exact same definition_hash,
           schema_version, engine_version, and experience_id.
        """
        inp = (
            input_data
            if isinstance(input_data, PublishReportInput)
            else PublishReportInput.model_validate(dict(input_data))
        )

        val_report = self._store.get_validation(inp.validation_id)
        if val_report is None:
            return False, f"Validation report '{inp.validation_id}' not found"

        if val_report.status != ValidationStatus.PASSED:
            return (
                False,
                f"Validation report status is '{val_report.status}', expected 'passed'",
            )

        if not val_report.mandatory_passed:
            return False, "Validation report mandatory checks failed"

        if val_report.experience_id != inp.experience_id:
            return (
                False,
                f"Validation report experience ID '{val_report.experience_id}' does not match '{inp.experience_id}'",
            )

        if val_report.content_hash != inp.definition_hash:
            return (
                False,
                f"Validation report content hash '{val_report.content_hash}' does not match '{inp.definition_hash}'",
            )

        if val_report.definition_schema_version != inp.definition_schema_version:
            return (
                False,
                f"Validation report schema version '{val_report.definition_schema_version}' does not match '{inp.definition_schema_version}'",
            )

        if val_report.engine_version != inp.engine_version:
            return (
                False,
                f"Validation report engine version '{val_report.engine_version}' does not match '{inp.engine_version}'",
            )

        eval_report = self._store.get_evaluation(inp.evaluation_id)
        if eval_report is None:
            return False, f"Evaluation report '{inp.evaluation_id}' not found"

        if eval_report.status != ValidationStatus.PASSED:
            return (
                False,
                f"Evaluation report status is '{eval_report.status}', expected 'passed'",
            )

        if not eval_report.mandatory_passed:
            return False, "Evaluation report mandatory golden cases failed"

        if eval_report.experience_id != inp.experience_id:
            return (
                False,
                f"Evaluation report experience ID '{eval_report.experience_id}' does not match '{inp.experience_id}'",
            )

        if eval_report.content_hash != inp.definition_hash:
            return (
                False,
                f"Evaluation report content hash '{eval_report.content_hash}' does not match '{inp.definition_hash}'",
            )

        if eval_report.definition_schema_version != inp.definition_schema_version:
            return (
                False,
                f"Evaluation report schema version '{eval_report.definition_schema_version}' does not match '{inp.definition_schema_version}'",
            )

        if eval_report.engine_version != inp.engine_version:
            return (
                False,
                f"Evaluation report engine version '{eval_report.engine_version}' does not match '{inp.engine_version}'",
            )

        return True, None
