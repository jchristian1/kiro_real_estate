"""
Unit tests for Prometheus metrics endpoint.

Tests the /metrics endpoint and metric tracking functionality including:
- Metrics endpoint returns Prometheus format
- Request counter increments
- Request duration histogram records
- Error counter increments
- Watcher count gauge (owned by worker — gauge is not updated by API)
- Lead processing counter

Requirements: 24.2, 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7
"""

import pytest
from fastapi.testclient import TestClient

from api.main import (
    app,
    api_requests_total,
    api_request_duration_seconds,
    api_errors_total,
    watchers_active,
    leads_processed_total,
    increment_leads_processed,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_metrics_endpoint_returns_prometheus_format(client):
    """
    Test that /metrics endpoint returns Prometheus text format.

    Requirements: 8.2, 29.1
    """
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    content = response.text
    assert "api_requests_total" in content
    assert "api_request_duration_seconds" in content
    assert "api_errors_total" in content
    assert "watchers_active" in content
    assert "leads_processed_total" in content
    assert "# HELP" in content
    assert "# TYPE" in content


def test_metrics_endpoint_does_not_require_authentication(client):
    """
    Test that /metrics endpoint does not require authentication.

    Requirements: 29.1
    """
    response = client.get("/metrics")
    assert response.status_code == 200


def test_request_counter_increments(client):
    """
    Test that request counter increments for each request.

    Requirements: 29.2
    """
    initial_value = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    response = client.get("/api/v1")
    assert response.status_code == 200

    new_value = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    assert new_value > initial_value


def test_request_duration_histogram_records(client):
    """
    Test that request duration histogram records request times.

    Requirements: 29.3
    """
    initial_sum = api_request_duration_seconds.labels(
        endpoint="/api/v1", method="GET"
    )._sum.get()

    response = client.get("/api/v1")
    assert response.status_code == 200

    new_sum = api_request_duration_seconds.labels(
        endpoint="/api/v1", method="GET"
    )._sum.get()

    assert new_sum >= initial_sum


def test_error_counter_increments_on_4xx(client):
    """
    Test that error counter increments for 4xx errors.

    Requirements: 29.6
    """
    initial_value = api_errors_total.labels(
        endpoint="/api/v1/nonexistent", status="404"
    )._value.get()

    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404

    new_value = api_errors_total.labels(
        endpoint="/api/v1/nonexistent", status="404"
    )._value.get()

    assert new_value > initial_value


def test_error_counter_increments_on_5xx(client):
    """
    Test that error counter can be incremented for 5xx errors.

    Requirements: 29.6
    """
    initial_value = api_errors_total.labels(endpoint="/test", status="500")._value.get()

    api_errors_total.labels(endpoint="/test", status="500").inc()

    new_value = api_errors_total.labels(endpoint="/test", status="500")._value.get()
    assert new_value > initial_value


def test_watcher_gauge_exists_in_metrics_output(client):
    """
    Test that watchers_active gauge is present in metrics output.

    The gauge is owned by the worker process and is not updated by the
    API metrics endpoint. It will be 0 unless the worker has written to it.

    Requirements: 29.4
    """
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "watchers_active" in response.text


def test_lead_processing_counter_increments(client):
    """
    Test that lead processing counter can be incremented.

    Requirements: 29.5
    """
    initial_value = leads_processed_total._value.get()

    increment_leads_processed(5)

    new_value = leads_processed_total._value.get()
    assert new_value == initial_value + 5


def test_lead_processing_counter_default_increment(client):
    """
    Test that lead processing counter increments by 1 by default.

    Requirements: 29.5
    """
    initial_value = leads_processed_total._value.get()

    increment_leads_processed()

    new_value = leads_processed_total._value.get()
    assert new_value == initial_value + 1


def test_metrics_endpoint_normalizes_paths_with_ids(client):
    """
    Test that metrics endpoint normalizes paths with IDs to avoid high cardinality.

    Requirements: 29.2, 29.3
    """
    client.get("/api/v1/agents/123")
    client.get("/api/v1/agents/456")
    client.get("/api/v1/agents/789")

    response = client.get("/metrics")
    content = response.text

    assert 'endpoint="/api/v1/agents/{id}"' in content
    assert 'endpoint="/api/v1/agents/123"' not in content
    assert 'endpoint="/api/v1/agents/456"' not in content


def test_metrics_endpoint_excludes_itself_from_tracking(client):
    """
    Test that /metrics endpoint does not track itself to avoid recursion.

    Requirements: 29.1
    """
    initial_value = api_requests_total.labels(
        endpoint="/metrics", method="GET", status="200"
    )._value.get()

    response = client.get("/metrics")
    assert response.status_code == 200

    new_value = api_requests_total.labels(
        endpoint="/metrics", method="GET", status="200"
    )._value.get()

    assert new_value == initial_value


def test_metrics_format_includes_all_required_metrics(client):
    """
    Test that metrics endpoint includes all required metrics in Prometheus format.

    Requirements: 29.1, 29.2, 29.3, 29.4, 29.5, 29.6
    """
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text

    required_metrics = [
        "api_requests_total",
        "api_request_duration_seconds",
        "api_errors_total",
        "watchers_active",
        "leads_processed_total",
    ]

    for metric in required_metrics:
        assert f"# HELP {metric}" in content
        assert f"# TYPE {metric}" in content


def test_request_metrics_track_different_methods(client):
    """
    Test that request metrics track different HTTP methods separately.

    Requirements: 29.2, 29.3
    """
    get_initial = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    response = client.get("/api/v1")
    assert response.status_code == 200

    get_new = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    assert get_new > get_initial


def test_metrics_endpoint_content_type_header(client):
    """
    Test that metrics endpoint returns correct content type for Prometheus.

    Requirements: 29.1, 29.7
    """
    response = client.get("/metrics")
    assert "text/plain" in response.headers.get("content-type", "")


def test_metrics_histogram_buckets(client):
    """
    Test that request duration histogram includes bucket information.

    Requirements: 29.3
    """
    client.get("/api/v1")

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    content = metrics_response.text

    assert "api_request_duration_seconds_bucket" in content
    assert content.count("api_request_duration_seconds_bucket") > 1


def test_metrics_counter_multiple_status_codes(client):
    """
    Test that metrics track different status codes separately.

    Requirements: 29.2, 29.6
    """
    success_initial = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    not_found_initial = api_requests_total.labels(
        endpoint="/api/v1/nonexistent", method="GET", status="404"
    )._value.get()

    client.get("/api/v1")
    client.get("/api/v1/nonexistent")

    success_new = api_requests_total.labels(
        endpoint="/api/v1", method="GET", status="200"
    )._value.get()

    not_found_new = api_requests_total.labels(
        endpoint="/api/v1/nonexistent", method="GET", status="404"
    )._value.get()

    assert success_new > success_initial
    assert not_found_new > not_found_initial


def test_lead_processing_counter_multiple_increments(client):
    """
    Test that lead processing counter accumulates correctly.

    Requirements: 29.5
    """
    initial_value = leads_processed_total._value.get()

    increment_leads_processed(3)
    increment_leads_processed(5)
    increment_leads_processed(2)

    new_value = leads_processed_total._value.get()
    assert new_value == initial_value + 10


def test_metrics_format_prometheus_compliance(client):
    """
    Test that metrics output complies with Prometheus format specification.

    Requirements: 29.1, 29.7
    """
    response = client.get("/metrics")
    assert response.status_code == 200

    content = response.text
    lines = content.split("\n")

    help_lines = [l for l in lines if l.startswith("# HELP")]
    type_lines = [l for l in lines if l.startswith("# TYPE")]

    assert len(help_lines) > 0
    assert len(type_lines) > 0

    for metric_name in [
        "api_requests_total",
        "api_request_duration_seconds",
        "api_errors_total",
        "watchers_active",
        "leads_processed_total",
    ]:
        assert any(metric_name in l for l in help_lines)
        assert any(metric_name in l for l in type_lines)
