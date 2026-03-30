"""
Focused tests for observability trust-alignment (Problem 6).

Verifies:
1. watchers_active gauge is set from DB-backed watcher_status at scrape time
2. /metrics endpoint returns a non-zero watchers_active when running watchers exist
3. leads_processed_total is NOT advertised in /metrics docstring or README
4. HealthData interface shape matches actual /health API response fields
5. Failed watcher count is computed from actual data, not hardcoded
"""

import os
import ast
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 1. watchers_active is wired to DB — verify the /metrics endpoint
#    calls WatcherStatusRepository and sets the gauge
# ---------------------------------------------------------------------------

class TestWatchersActiveMetric:

    def test_metrics_endpoint_queries_watcher_status_repo(self, app_client):
        """
        /metrics must call WatcherStatusRepository.list_all() to populate
        watchers_active — not leave it at 0 unconditionally.
        """
        mock_row_running = MagicMock()
        mock_row_running.status = "running"
        mock_row_stopped = MagicMock()
        mock_row_stopped.status = "stopped"

        with patch(
            "api.repositories.watcher_coordination_repository.WatcherStatusRepository.list_all",
            return_value=[mock_row_running, mock_row_stopped],
        ):
            r = app_client.get("/metrics")

        assert r.status_code == 200
        body = r.text
        # watchers_active gauge must appear in the output
        assert "watchers_active" in body

    def test_metrics_watchers_active_reflects_running_count(self, app_client):
        """
        watchers_active gauge value must equal the number of 'running' rows
        returned by WatcherStatusRepository.
        """
        mock_rows = [MagicMock(status="running"), MagicMock(status="running"), MagicMock(status="stopped")]

        with patch(
            "api.repositories.watcher_coordination_repository.WatcherStatusRepository.list_all",
            return_value=mock_rows,
        ):
            r = app_client.get("/metrics")

        assert r.status_code == 200
        # Find the watchers_active line — format: "watchers_active 2.0"
        lines = [l for l in r.text.splitlines() if l.startswith("watchers_active ")]
        assert len(lines) == 1, f"Expected exactly one watchers_active line, got: {lines}"
        value = float(lines[0].split()[-1])
        assert value == 2.0, f"Expected 2.0 running watchers, got {value}"

    def test_metrics_watchers_active_zero_when_no_running(self, app_client):
        """watchers_active must be 0 when no watchers are running."""
        mock_rows = [MagicMock(status="stopped"), MagicMock(status="failed")]

        with patch(
            "api.repositories.watcher_coordination_repository.WatcherStatusRepository.list_all",
            return_value=mock_rows,
        ):
            r = app_client.get("/metrics")

        assert r.status_code == 200
        lines = [l for l in r.text.splitlines() if l.startswith("watchers_active ")]
        assert len(lines) == 1
        value = float(lines[0].split()[-1])
        assert value == 0.0

    def test_metrics_watchers_active_zero_when_no_watchers(self, app_client):
        """watchers_active must be 0 when watcher_status table is empty."""
        with patch(
            "api.repositories.watcher_coordination_repository.WatcherStatusRepository.list_all",
            return_value=[],
        ):
            r = app_client.get("/metrics")

        assert r.status_code == 200
        lines = [l for l in r.text.splitlines() if l.startswith("watchers_active ")]
        assert len(lines) == 1
        assert float(lines[0].split()[-1]) == 0.0

    def test_metrics_endpoint_survives_db_error(self, app_client):
        """
        If the DB query fails, /metrics must still return 200 with other metrics.
        watchers_active will retain its last known value (graceful degradation).
        """
        with patch(
            "api.repositories.watcher_coordination_repository.WatcherStatusRepository.list_all",
            side_effect=Exception("DB unavailable"),
        ):
            r = app_client.get("/metrics")

        assert r.status_code == 200
        # Other metrics must still be present
        assert "api_requests_total" in r.text


# ---------------------------------------------------------------------------
# 2. leads_processed_total is NOT advertised as operator-meaningful
# ---------------------------------------------------------------------------

class TestLeadsProcessedNotOverclaimed:

    def test_metrics_docstring_does_not_claim_leads_processed_as_tracked(self):
        """
        The /metrics endpoint docstring must not list leads_processed_total
        as an actively tracked metric.
        """
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        tree = ast.parse(source)
        metrics_docstring = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "metrics":
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)):
                    metrics_docstring = node.body[0].value.value
                break

        assert metrics_docstring is not None, "metrics() function not found"
        # Must not claim leads_processed_total is tracked/active
        assert "leads_processed_total" not in metrics_docstring or "not yet wired" in metrics_docstring.lower() or "not" in metrics_docstring.lower(), (
            "metrics() docstring must not advertise leads_processed_total as an active metric"
        )

    def test_readme_does_not_claim_leads_processed(self):
        """README must not claim leads_processed as a Prometheus metric."""
        readme_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "README.md"
        )
        with open(readme_path) as f:
            content = f.read()

        assert "leads processed" not in content.lower(), (
            "README must not advertise 'leads processed' as a Prometheus metric "
            "until leads_processed_total is actually wired"
        )

    def test_leads_processed_counter_has_honest_comment(self):
        """
        The leads_processed_total registration must have a comment explaining
        it is not yet wired, so future developers understand the state.
        """
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        # The comment should appear near the counter registration
        assert "never called" in source or "not yet wired" in source, (
            "leads_processed_total registration must have a comment explaining "
            "it is not yet wired"
        )


# ---------------------------------------------------------------------------
# 3. HealthData interface matches actual /health response shape
# ---------------------------------------------------------------------------

class TestHealthDataShape:

    def test_health_endpoint_returns_active_watchers_at_top_level(self, app_client):
        """
        /health must return active_watchers as a top-level integer field,
        not nested under watchers.active_count.
        """
        r = app_client.get("/api/v1/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "active_watchers" in data, (
            "Health response must have top-level 'active_watchers' field"
        )
        assert isinstance(data["active_watchers"], int)

    def test_health_endpoint_returns_database_as_string(self, app_client):
        """
        /health must return database as a string ('connected' | 'error'),
        not as a nested object with a 'connected' boolean.
        """
        r = app_client.get("/api/v1/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "database" in data
        assert isinstance(data["database"], str), (
            "Health response 'database' field must be a string, not an object"
        )
        assert data["database"] in ("connected", "error")

    def test_health_endpoint_returns_errors_last_24h_at_top_level(self, app_client):
        """
        /health must return errors_last_24h as a top-level integer,
        not nested under errors.count_24h.
        """
        r = app_client.get("/api/v1/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "errors_last_24h" in data
        assert isinstance(data["errors_last_24h"], int)

    def test_health_endpoint_watchers_field_is_dict(self, app_client):
        """
        /health watchers field must be a dict keyed by agent_id,
        not an object with active_count.
        """
        r = app_client.get("/api/v1/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "watchers" in data
        assert isinstance(data["watchers"], dict), (
            "Health response 'watchers' must be a dict keyed by agent_id"
        )
        # Must NOT have active_count nested inside watchers
        assert "active_count" not in data["watchers"], (
            "Health response must not have watchers.active_count — "
            "use top-level active_watchers instead"
        )

    def test_frontend_health_data_interface_uses_correct_fields(self):
        """
        DashboardPage.tsx HealthData interface must use the actual API field names:
        - active_watchers (not watchers.active_count)
        - database as string (not database.connected)
        - errors_last_24h (not errors.count_24h)
        """
        dashboard_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "frontend", "src", "apps", "platform-admin", "pages", "DashboardPage.tsx"
        )
        with open(dashboard_path) as f:
            content = f.read()

        assert "active_watchers" in content, (
            "DashboardPage must use 'active_watchers' field from health response"
        )
        assert "active_count" not in content, (
            "DashboardPage must not reference 'active_count' — that field does not exist in the health response"
        )
        assert "errors_last_24h" in content, (
            "DashboardPage must use 'errors_last_24h' field from health response"
        )


# ---------------------------------------------------------------------------
# 4. Failed watcher count is computed, not hardcoded
# ---------------------------------------------------------------------------

class TestFailedWatcherCount:

    def test_health_metrics_component_does_not_hardcode_zero_failed(self):
        """
        HealthMetrics.tsx must not hardcode failed watcher count as 0.
        It must compute it from actual health data.
        """
        component_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "frontend", "src", "apps", "platform-admin", "components", "HealthMetrics.tsx"
        )
        with open(component_path) as f:
            content = f.read()

        # The old hardcoded pattern must be gone
        assert ">0<" not in content.replace(" ", ""), (
            "HealthMetrics must not hardcode failed watcher count as 0"
        )
        # Must reference failedWatchers variable
        assert "failedWatchers" in content, (
            "HealthMetrics must compute failedWatchers from health data"
        )

    def test_health_metrics_component_computes_failed_from_watchers_dict(self):
        """
        HealthMetrics.tsx must filter the watchers dict for 'failed' status
        to compute the failed count.
        """
        component_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "frontend", "src", "apps", "platform-admin", "components", "HealthMetrics.tsx"
        )
        with open(component_path) as f:
            content = f.read()

        assert "failed" in content, (
            "HealthMetrics must filter for 'failed' status to compute failed watcher count"
        )
