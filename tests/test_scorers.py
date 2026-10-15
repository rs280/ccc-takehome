from evals.scorers import citation_grounding, deploy_attribution, passed, score_run
from incident_agent.evidence import EvidenceLedger
from incident_agent.schemas import IncidentReport

EXPECTED = {
    "category": "bad_config",
    "acceptable_categories": ["bad_config", "code_bug"],
    "caused_by_latest_deploy": True,
    "key_facts": ["v2.4.1", "DATABASE_POOL_SIZE"],
    "expected_tools": ["get_recent_deployments", "search_logs|get_error_summary"],
    "next_step_keywords": ["roll back"],
}


def ledger():
    led = EvidenceLedger()
    led.add(
        "changes", "get_recent_deployments", {}, '[{"version": "v2.4.1", "deployed_at": "10:02"}]'
    )
    led.add(
        "logs",
        "get_error_summary",
        {},
        "KeyError: 'DATABASE_POOL_SIZE' (app/config/settings.py:41)",
    )
    return led


def report(**overrides):
    data = {
        "summary": "s",
        "incident_type": "5xx",
        "affected_services": ["checkout-api"],
        "evidence": [
            {"evidence_id": "E1", "source": "deployments", "detail": "v2.4.1 deployed at 10:02"},
            {
                "evidence_id": "E2",
                "source": "logs",
                "detail": "KeyError DATABASE_POOL_SIZE in settings.py",
            },
        ],
        "root_cause": {
            "hypothesis": "env var renamed",
            "category": "bad_config",
            "confidence": 0.85,
        },
        "caused_by_latest_deploy": True,
        "next_steps": [{"action": "Roll back to v2.4.0", "priority": "P0"}],
    }
    data.update(overrides)
    return IncidentReport.model_validate(data)


def test_good_report_passes_everything():
    scores = score_run(report(), ledger(), EXPECTED)
    assert all(s.passed for s in scores), [s for s in scores if not s.passed]
    assert passed(scores)


def test_hallucinated_id_and_fact_fail_grounding():
    bad = report(
        evidence=[
            {"evidence_id": "E7", "source": "logs", "detail": "anything"},
            {
                "evidence_id": "E2",
                "source": "logs",
                "detail": "OutOfMemoryError in worker_pool.py at 512Mi",
            },
        ]
    )
    score = citation_grounding(bad, ledger())
    assert score.value == 0.0 and "E7" in score.detail and "unsupported" in score.detail


def test_wrong_category_fails_and_overconfidence_is_flagged():
    bad = report(
        root_cause={"hypothesis": "db down", "category": "dependency_failure", "confidence": 0.9}
    )
    scores = {s.name: s for s in score_run(bad, ledger(), EXPECTED)}
    assert not scores["root_cause_category"].passed
    assert not scores["calibration"].passed
    assert not passed(list(scores.values()))


def test_undetermined_truth_rejects_blaming_deploy_only():
    want_none = {**EXPECTED, "caused_by_latest_deploy": None}
    assert deploy_attribution(report(caused_by_latest_deploy=None), want_none).passed
    assert deploy_attribution(report(caused_by_latest_deploy=False), want_none).passed
    assert not deploy_attribution(report(caused_by_latest_deploy=True), want_none).passed


def test_missing_report_fails():
    assert not passed(score_run(None, None, EXPECTED))


def test_grounding_tolerates_paraphrase_but_not_invented_identifiers():
    """Regression: a correct report failed because English words like 'configuration' and
    'deployment' were required verbatim. Only identifiers and numbers are facts to check."""
    led = EvidenceLedger()
    led.add("logs", "get_error_summary", {}, "Unhandled exception: KeyError: 'DATABASE_POOL_SIZE'")
    paraphrase = report(
        evidence=[
            {
                "evidence_id": "E1",
                "source": "logs",
                "detail": "checkout-api experienced errors after the deployment due to missing configuration DATABASE_POOL_SIZE",
            }
        ]
    )
    assert citation_grounding(paraphrase, led).value == 1.0
    invented = report(
        evidence=[
            {
                "evidence_id": "E1",
                "source": "logs",
                "detail": "OutOfMemoryError at 512Mi in worker_pool.py",
            }
        ]
    )
    assert citation_grounding(invented, led).value == 0.0


def test_grounding_matches_numbers_written_with_units():
    """Regression: '201.68ms' was unsupported against raw output containing 201.68."""
    led = EvidenceLedger()
    led.add("metrics", "get_metrics", {}, '{"median_before":201.68,"median_after":5081.27}')
    with_units = report(
        evidence=[
            {
                "evidence_id": "E1",
                "source": "metrics",
                "detail": "p99 latency rose from 201.68ms to 5081.27ms",
            }
        ]
    )
    assert citation_grounding(with_units, led).value == 1.0
