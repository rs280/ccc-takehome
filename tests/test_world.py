import pytest

from incident_agent.mcp_server.world import World, WorldError, available_scenarios


@pytest.fixture(scope="module")
def world():
    return World.load("checkout_bad_config")


def test_all_scenarios_load_and_have_ground_truth():
    import json

    names = available_scenarios()
    assert len(names) == 7
    for name in names:
        w = World.load(name)
        assert w.incident and w.logs and w.deployments and w.docs
        expected = json.loads((w.root / "expected.json").read_text())
        assert {
            "category",
            "caused_by_latest_deploy",
            "key_facts",
            "expected_tools",
        } <= expected.keys()


def test_unknown_scenario():
    with pytest.raises(WorldError, match="Available"):
        World.load("nope")


def test_recent_deployments_newest_first_without_diff(world):
    deps = world.get_recent_deployments("checkout-api")
    assert [d["version"] for d in deps] == ["v2.4.1", "v2.4.0"]
    assert "diff" not in deps[0]


def test_deployment_diff(world):
    diff = world.get_deployment_diff("dep-7715")
    assert diff["version"] == "v2.4.1"
    assert any("DATABASE_POOL_SIZE" in c for c in diff["commits"])
    with pytest.raises(WorldError, match="Known"):
        world.get_deployment_diff("dep-0000")


def test_search_logs_filters(world):
    res = world.search_logs("checkout-api", query="keyerror database_pool_size", level="error")
    assert res["total_matches"] > 10
    assert res["first_match_ts"] >= "2026-10-14T10:02:00Z"
    assert all(line["level"] == "ERROR" for line in res["lines"])
    assert res["lines"][0]["ts"] >= res["lines"][-1]["ts"]  # newest first


def test_search_logs_time_window_and_bad_inputs(world):
    res = world.search_logs("checkout-api", level="ERROR", until="2026-10-14T10:00:00Z")
    assert res["total_matches"] == 0
    with pytest.raises(WorldError, match="Unknown service"):
        world.search_logs("checkout")
    with pytest.raises(WorldError, match="Invalid timestamp"):
        world.search_logs("checkout-api", since="yesterday")


def test_error_summary_pivots_on_latest_deploy(world):
    summary = world.get_error_summary("checkout-api")
    assert summary["pivot"] == "2026-10-14T10:02:00Z"
    top = summary["groups"][0]
    assert "KeyError" in top["example"]
    assert top.get("before_pivot", 0) == 0 and top["after_pivot"] > 10


def test_error_summary_shows_errors_predating_deploy():
    w = World.load("orders_upstream_dependency")
    top = w.get_error_summary("orders-api")["groups"][0]
    assert "inventory-service timeout" in top["example"]
    assert top["before_pivot"] > 0  # errors began before the v1.9.3 deploy


def test_metrics_detects_change(world):
    m = world.get_metrics("checkout-api", "error_rate")
    assert m["change"]["median_before"] < 1 and m["change"]["median_after"] > 30
    assert m["change"]["at"] == "2026-10-14T10:10:00Z"
    with pytest.raises(WorldError, match="Available"):
        world.get_metrics("checkout-api", "qps")


def test_search_docs_ranks_relevant_doc(world):
    hits = world.search_docs("missing environment variable KeyError config")
    assert hits[0]["doc"] == "config-management"
    with pytest.raises(WorldError):
        world.search_docs("a")


def test_error_summary_does_not_split_on_deploy_older_than_logs():
    """A deploy days before the log window must not make every error look 'after deploy'."""
    w = World.load("auth_cert_expiry")
    summary = w.get_error_summary("auth-api")
    assert summary["pivot"] is None
    assert "before the earliest available log" in summary["note"]
    top = summary["groups"][0]
    assert "CERTIFICATE_VERIFY_FAILED" in top["example"]
    assert "before" not in top and top["count"] > 100


def test_deployments_report_age_relative_to_now():
    w = World.load("auth_cert_expiry")
    (dep,) = w.get_recent_deployments("auth-api")
    assert dep["hours_before_now"] > 100


def test_metrics_ignore_noise_but_catch_sustained_steps():
    noisy = World.load("ambiguous_low_signal").get_metrics("profile-api", "error_rate")
    assert isinstance(noisy["change"], str) and "no significant change" in noisy["change"]
    step = World.load("auth_cert_expiry").get_metrics("auth-api", "error_rate")
    assert step["change"]["at"] == "2026-10-14T10:00:00Z"


def test_change_point_located_at_the_step_not_before_it():
    w = World.load("orders_upstream_dependency")
    m = w.get_metrics("inventory-service", "db_connections_in_use")
    assert m["change"]["at"] == "2026-10-14T09:20:00Z"
    assert m["change"]["median_after"] == 20


def test_error_groups_state_timing_relative_to_latest_deploy():
    """Models compare ISO timestamps unreliably, so the tool says 'before'/'after' in words."""
    w = World.load("orders_upstream_dependency")
    top = w.get_error_summary("orders-api")["groups"][0]
    assert top["first_seen_vs_latest_deploy"] == "50 min BEFORE latest deploy dep-7716 (v1.9.3)"
    w = World.load("checkout_bad_config")
    top = w.get_error_summary("checkout-api")["groups"][0]
    assert top["first_seen_vs_latest_deploy"].startswith("1 min AFTER latest deploy dep-7715")


def test_metric_change_states_timing_relative_to_latest_deploy():
    m = World.load("orders_upstream_dependency").get_metrics("orders-api", "error_rate")
    assert m["change"]["vs_latest_deploy"] == "50 min BEFORE latest deploy dep-7716 (v1.9.3)"


def test_metrics_without_change_offer_no_cherry_pickable_endpoints():
    m = World.load("ambiguous_low_signal").get_metrics("profile-api", "error_rate")
    assert "latest" not in m and "baseline" not in m
    assert m["summary"]["min"] <= m["summary"]["median"] <= m["summary"]["max"]
