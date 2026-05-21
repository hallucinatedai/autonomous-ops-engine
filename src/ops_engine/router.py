"""AI workflow router - maps user intent to workflow type using keyword matching (MVP)."""

from ops_engine.models import WorkflowType


class WorkflowRouter:
    """Route user intent to appropriate workflow type using keyword matching."""

    INTENT_KEYWORDS: dict[WorkflowType, list[str]] = {
        WorkflowType.DEPLOYMENT: [
            "deploy",
            "release",
            "rollout",
            "ship",
            "publish",
            "push to production",
            "go live",
            "launch",
        ],
        WorkflowType.INCIDENT_RESPONSE: [
            "incident",
            "outage",
            "down",
            "alert",
            "failure",
            "crash",
            "emergency",
            "p1",
            "sev1",
            "broken",
            "degraded",
        ],
        WorkflowType.CHANGE_REQUEST: [
            "change",
            "modify",
            "update",
            "alter",
            "request",
            "rfc",
            "change request",
            "configuration change",
        ],
        WorkflowType.MAINTENANCE: [
            "maintenance",
            "patch",
            "upgrade",
            "backup",
            "cleanup",
            "housekeeping",
            "scheduled",
            "routine",
        ],
        WorkflowType.ONBOARDING: [
            "onboard",
            "new hire",
            "access",
            "provision",
            "setup",
            "welcome",
            "new employee",
            "join",
        ],
    }

    def __init__(self, custom_keywords: dict[WorkflowType, list[str]] | None = None):
        self._keywords = dict(self.INTENT_KEYWORDS)
        if custom_keywords:
            for wf_type, keywords in custom_keywords.items():
                self._keywords.setdefault(wf_type, []).extend(keywords)

    def route(self, intent: str) -> WorkflowType:
        """Map a user intent string to a workflow type."""
        intent_lower = intent.lower().strip()

        scores: dict[WorkflowType, int] = {}

        for wf_type, keywords in self._keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in intent_lower:
                    score += len(keyword)
            if score > 0:
                scores[wf_type] = score

        if not scores:
            return WorkflowType.CUSTOM

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def get_confidence(self, intent: str) -> tuple[WorkflowType, float]:
        """Route with confidence score (0.0 to 1.0)."""
        intent_lower = intent.lower().strip()

        scores: dict[WorkflowType, int] = {}
        total_score = 0

        for wf_type, keywords in self._keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in intent_lower:
                    score += len(keyword)
            if score > 0:
                scores[wf_type] = score
                total_score += score

        if not scores:
            return WorkflowType.CUSTOM, 0.0

        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        confidence = scores[best_type] / total_score if total_score > 0 else 0.0

        return best_type, round(confidence, 2)
