"""Tests for the workflow router."""

import pytest

from ops_engine.models import WorkflowType
from ops_engine.router import WorkflowRouter


@pytest.fixture
def router() -> WorkflowRouter:
    return WorkflowRouter()


class TestWorkflowRouter:
    def test_route_deployment(self, router: WorkflowRouter):
        assert router.route("deploy the application to production") == WorkflowType.DEPLOYMENT

    def test_route_incident(self, router: WorkflowRouter):
        assert router.route("critical outage on the API") == WorkflowType.INCIDENT_RESPONSE

    def test_route_change_request(self, router: WorkflowRouter):
        assert router.route("submit a change request for config") == WorkflowType.CHANGE_REQUEST

    def test_route_maintenance(self, router: WorkflowRouter):
        assert router.route("schedule maintenance window") == WorkflowType.MAINTENANCE

    def test_route_onboarding(self, router: WorkflowRouter):
        assert router.route("onboard new employee") == WorkflowType.ONBOARDING

    def test_route_unknown_defaults_to_custom(self, router: WorkflowRouter):
        assert router.route("something completely random xyz") == WorkflowType.CUSTOM

    def test_route_case_insensitive(self, router: WorkflowRouter):
        assert router.route("DEPLOY the APP") == WorkflowType.DEPLOYMENT

    def test_route_multiple_keywords(self, router: WorkflowRouter):
        result = router.route("release and deploy to production and go live")
        assert result == WorkflowType.DEPLOYMENT

    def test_confidence_high_match(self, router: WorkflowRouter):
        wf_type, confidence = router.get_confidence("deploy release to production")
        assert wf_type == WorkflowType.DEPLOYMENT
        assert confidence > 0.5

    def test_confidence_no_match(self, router: WorkflowRouter):
        wf_type, confidence = router.get_confidence("xyz abc 123")
        assert wf_type == WorkflowType.CUSTOM
        assert confidence == 0.0

    def test_custom_keywords(self):
        custom = {WorkflowType.CUSTOM: ["special", "unique"]}
        router = WorkflowRouter(custom_keywords=custom)
        assert router.route("this is a special unique task") == WorkflowType.CUSTOM
