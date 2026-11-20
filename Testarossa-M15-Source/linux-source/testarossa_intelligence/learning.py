"""Controlled learning and recovery recommendations. Never executes repairs."""
from dataclasses import dataclass
from collections import Counter


VALID_OUTCOMES = {"success", "failure", "blocked", "cancelled"}
VALID_ACTIONS = {
    "inspect",
    "retry_once",
    "revise_plan",
    "request_approval",
    "stop_and_report",
}


@dataclass(frozen=True)
class RecoveryAdvice:
    action: str
    reason: str
    retry_allowed: bool


@dataclass(frozen=True)
class SkillProposal:
    name: str
    description: str
    procedure: tuple[str, ...]
    evidence_count: int
    requires_review: bool = True


class LearningEngine:
    """Turns recorded outcomes into bounded advice and reviewable proposals."""

    def analyze_history(self, records):
        if type(records) is not list or len(records) > 1000:
            raise ValueError("invalid_history")

        valid = []
        for record in records:
            if type(record) is not dict:
                raise ValueError("invalid_record")
            if set(record) - {"outcome", "error", "operation"}:
                raise ValueError("unknown_record_field")
            if record.get("outcome") not in VALID_OUTCOMES:
                raise ValueError("invalid_outcome")
            for field in ("error", "operation"):
                value = record.get(field, "")
                if type(value) is not str or len(value) > 500:
                    raise ValueError("invalid_record_text")
            valid.append(record)

        counts = Counter(record["outcome"] for record in valid)
        errors = Counter(
            record["error"].strip()
            for record in valid
            if record["outcome"] == "failure" and record.get("error", "").strip()
        )

        return {
            "total": len(valid),
            "outcomes": dict(counts),
            "recurring_errors": [
                {"error": error, "count": count}
                for error, count in errors.most_common(10)
                if count >= 2
            ],
        }

    def recommend_recovery(
        self,
        outcome,
        error="",
        retry_count=0,
        approval_required=False,
    ):
        if outcome not in VALID_OUTCOMES:
            raise ValueError("invalid_outcome")
        if type(error) is not str or len(error) > 500:
            raise ValueError("invalid_error")
        if type(retry_count) is not int or not 0 <= retry_count <= 100:
            raise ValueError("invalid_retry_count")
        if type(approval_required) is not bool:
            raise ValueError("invalid_approval_flag")

        if outcome == "success":
            return RecoveryAdvice(
                "inspect", "Verify the result before recording success.", False
            )

        if outcome == "blocked":
            return RecoveryAdvice(
                "request_approval",
                "The operation was blocked by a permission boundary.",
                False,
            )

        if outcome == "cancelled":
            return RecoveryAdvice(
                "stop_and_report",
                "The operation was cancelled; do not restart it automatically.",
                False,
            )

        if approval_required:
            return RecoveryAdvice(
                "request_approval",
                "The operation requires explicit user approval.",
                False,
            )

        if retry_count == 0:
            return RecoveryAdvice(
                "inspect",
                "Inspect the failure and relevant state before retrying.",
                False,
            )

        if retry_count == 1:
            return RecoveryAdvice(
                "revise_plan",
                "The first retry did not resolve the issue; revise the plan.",
                False,
            )

        return RecoveryAdvice(
            "stop_and_report",
            "The retry budget is exhausted. Stop and report the failure.",
            False,
        )

    def propose_skill(
        self,
        name,
        description,
        procedure,
        evidence_count,
    ):
        if type(name) is not str or not name or len(name) > 64:
            raise ValueError("invalid_skill_name")
        if not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError("invalid_skill_name")
        if type(description) is not str or not description.strip() or len(description) > 500:
            raise ValueError("invalid_skill_description")
        if type(procedure) not in (list, tuple) or not 1 <= len(procedure) <= 30:
            raise ValueError("invalid_procedure")
        if any(
            type(step) is not str or not step.strip() or len(step) > 500
            for step in procedure
        ):
            raise ValueError("invalid_procedure_step")
        if type(evidence_count) is not int or evidence_count < 1:
            raise ValueError("invalid_evidence_count")

        return SkillProposal(
            name=name,
            description=description.strip(),
            procedure=tuple(step.strip() for step in procedure),
            evidence_count=evidence_count,
        )

    @staticmethod
    def approve_proposal(proposal, user_approved):
        if not isinstance(proposal, SkillProposal):
            raise ValueError("invalid_skill_proposal")
        if type(user_approved) is not bool:
            raise ValueError("approval_must_be_boolean")
        if not user_approved:
            raise PermissionError("explicit_user_approval_required")
        return {
            "name": proposal.name,
            "description": proposal.description,
            "procedure": list(proposal.procedure),
            "evidence_count": proposal.evidence_count,
        }
