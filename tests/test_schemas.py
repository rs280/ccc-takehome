import pytest
from pydantic import ValidationError

from incident_agent.schemas import IncidentReport


def sample(**overrides):
    data = {
        "summary": "500s after deploy",
        "incident_type": "elevated 5xx",
        "affected_services": ["checkout-api"],
        "evidence": [{"evidence_id": "E1", "source": "logs", "detail": "KeyError"}],
        "root_cause": {
            "hypothesis": "missing env var",
            "category": "bad_config",
            "confidence": 0.8,
        },
        "caused_by_latest_deploy": True,
        "next_steps": [{"action": "Roll back", "priority": "P0"}],
    }
    data.update(overrides)
    return data


def test_valid_report():
    report = IncidentReport.model_validate(sample())
    assert report.root_cause.category == "bad_config"
    assert report.open_questions == []


def test_rejects_unknown_category():
    bad = sample(root_cause={"hypothesis": "x", "category": "aliens", "confidence": 0.5})
    with pytest.raises(ValidationError):
        IncidentReport.model_validate(bad)


@pytest.mark.parametrize("confidence", [-0.1, 1.5])
def test_confidence_bounded(confidence):
    bad = sample(root_cause={"hypothesis": "x", "category": "unknown", "confidence": confidence})
    with pytest.raises(ValidationError):
        IncidentReport.model_validate(bad)


def test_caused_by_latest_deploy_allows_null():
    assert (
        IncidentReport.model_validate(sample(caused_by_latest_deploy=None)).caused_by_latest_deploy
        is None
    )


@pytest.mark.parametrize(
    ("raw", "value"), [("null", None), ("true", True), ("false", False), (None, None)]
)
def test_tristate_accepts_template_style_strings(raw, value):
    assert (
        IncidentReport.model_validate(sample(caused_by_latest_deploy=raw)).caused_by_latest_deploy
        is value
    )
