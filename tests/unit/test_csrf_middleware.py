"""
Unit tests for CSRFOriginMiddleware (api/middleware/csrf.py).

Covers:
- Safe methods (GET, HEAD, OPTIONS) are always allowed
- Mutating methods with a matching Origin are allowed
- Mutating methods with a mismatched Origin are blocked (403)
- Mutating methods with no Origin/Referer are allowed (non-browser clients)
- Referer fallback works when Origin is absent
- Exempt paths bypass the check
- Wildcard origins in the allowlist are ignored (not treated as allow-all)
- _origin_matches helper edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.csrf import CSRFOriginMiddleware, _origin_matches, _extract_origin


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestOriginMatches:
    def test_exact_match(self):
        assert _origin_matches("http://localhost:5173", ["http://localhost:5173"])

    def test_trailing_slash_normalised(self):
        assert _origin_matches("http://localhost:5173/", ["http://localhost:5173"])

    def test_different_port_rejected(self):
        assert not _origin_matches("http://localhost:3000", ["http://localhost:5173"])

    def test_different_scheme_rejected(self):
        assert not _origin_matches("https://localhost:5173", ["http://localhost:5173"])

    def test_wildcard_in_allowlist_ignored(self):
        # Wildcard must NOT be treated as allow-all
        assert not _origin_matches("http://evil.example.com", ["*"])

    def test_empty_allowlist_rejects_all(self):
        assert not _origin_matches("http://localhost:5173", [])

    def test_multiple_origins_first_matches(self):
        allowed = ["http://localhost:5173", "http://localhost:3000"]
        assert _origin_matches("http://localhost:3000", allowed)

    def test_malformed_origin_rejected(self):
        assert not _origin_matches("not-a-url", ["http://localhost:5173"])


# ---------------------------------------------------------------------------
# Integration tests via TestClient
# ---------------------------------------------------------------------------

ALLOWED = ["http://localhost:5173", "http://localhost:3000"]


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with the CSRF middleware attached."""
    app = FastAPI()
    app.add_middleware(CSRFOriginMiddleware, allowed_origins=ALLOWED)

    @app.get("/api/v1/resource")
    def get_resource():
        return {"ok": True}

    @app.post("/api/v1/resource")
    def post_resource():
        return {"ok": True}

    @app.put("/api/v1/resource")
    def put_resource():
        return {"ok": True}

    @app.patch("/api/v1/resource")
    def patch_resource():
        return {"ok": True}

    @app.delete("/api/v1/resource")
    def delete_resource():
        return {"ok": True}

    # Exempt paths
    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    @app.post("/api/v1/agent/auth/login")
    def agent_login():
        return {"ok": True}

    @app.post("/api/v1/agent/auth/signup")
    def agent_signup():
        return {"ok": True}

    @app.post("/api/v1/public/submit")
    def public_submit():
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"status": "healthy"}

    @app.get("/metrics")
    def metrics():
        return {}

    return app


@pytest.fixture(scope="module")
def client():
    return TestClient(_make_app(), raise_server_exceptions=True)


class TestSafeMethodsAlwaysAllowed:
    def test_get_no_origin(self, client):
        r = client.get("/api/v1/resource")
        assert r.status_code == 200

    def test_get_wrong_origin(self, client):
        r = client.get("/api/v1/resource", headers={"Origin": "http://evil.example.com"})
        assert r.status_code == 200

    def test_options_no_origin(self, client):
        r = client.options("/api/v1/resource")
        assert r.status_code in (200, 405)  # 405 = method not registered, still not 403


class TestMutatingMethodsAllowedOrigin:
    def test_post_allowed_origin(self, client):
        r = client.post("/api/v1/resource", headers={"Origin": "http://localhost:5173"})
        assert r.status_code == 200

    def test_put_allowed_origin(self, client):
        r = client.put("/api/v1/resource", headers={"Origin": "http://localhost:3000"})
        assert r.status_code == 200

    def test_patch_allowed_origin(self, client):
        r = client.patch("/api/v1/resource", headers={"Origin": "http://localhost:5173"})
        assert r.status_code == 200

    def test_delete_allowed_origin(self, client):
        r = client.delete("/api/v1/resource", headers={"Origin": "http://localhost:5173"})
        assert r.status_code == 200


class TestMutatingMethodsBlockedOrigin:
    def test_post_wrong_origin_blocked(self, client):
        r = client.post("/api/v1/resource", headers={"Origin": "http://evil.example.com"})
        assert r.status_code == 403

    def test_post_wrong_origin_error_code(self, client):
        r = client.post("/api/v1/resource", headers={"Origin": "http://evil.example.com"})
        assert r.json()["code"] == "CSRF_ORIGIN_MISMATCH"

    def test_put_wrong_origin_blocked(self, client):
        r = client.put("/api/v1/resource", headers={"Origin": "http://evil.example.com"})
        assert r.status_code == 403

    def test_delete_wrong_origin_blocked(self, client):
        r = client.delete("/api/v1/resource", headers={"Origin": "http://evil.example.com"})
        assert r.status_code == 403


class TestNoOriginHeader:
    """Requests with no Origin/Referer are non-browser clients — allowed through."""

    def test_post_no_origin_allowed(self, client):
        r = client.post("/api/v1/resource")
        assert r.status_code == 200

    def test_put_no_origin_allowed(self, client):
        r = client.put("/api/v1/resource")
        assert r.status_code == 200

    def test_delete_no_origin_allowed(self, client):
        r = client.delete("/api/v1/resource")
        assert r.status_code == 200


class TestRefererFallback:
    def test_post_allowed_referer_no_origin(self, client):
        r = client.post(
            "/api/v1/resource",
            headers={"Referer": "http://localhost:5173/some/page"},
        )
        assert r.status_code == 200

    def test_post_blocked_referer_no_origin(self, client):
        r = client.post(
            "/api/v1/resource",
            headers={"Referer": "http://evil.example.com/page"},
        )
        assert r.status_code == 403


class TestExemptPaths:
    def test_login_exempt(self, client):
        r = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://evil.example.com"},
            json={"username": "x", "password": "y"},
        )
        # Should not be blocked by CSRF (may fail auth, but not 403 CSRF)
        assert r.status_code != 403 or r.json().get("code") != "CSRF_ORIGIN_MISMATCH"

    def test_agent_login_exempt(self, client):
        r = client.post(
            "/api/v1/agent/auth/login",
            headers={"Origin": "http://evil.example.com"},
            json={"email": "x@x.com", "password": "y"},
        )
        assert r.status_code != 403 or r.json().get("code") != "CSRF_ORIGIN_MISMATCH"

    def test_agent_signup_exempt(self, client):
        r = client.post(
            "/api/v1/agent/auth/signup",
            headers={"Origin": "http://evil.example.com"},
            json={"email": "x@x.com", "password": "password123"},
        )
        assert r.status_code != 403 or r.json().get("code") != "CSRF_ORIGIN_MISMATCH"

    def test_public_submit_exempt(self, client):
        r = client.post(
            "/api/v1/public/submit",
            headers={"Origin": "http://evil.example.com"},
        )
        assert r.status_code != 403 or r.json().get("code") != "CSRF_ORIGIN_MISMATCH"


class TestWildcardOriginNotAllowed:
    def test_wildcard_in_allowlist_does_not_permit_arbitrary_origin(self):
        """Even if CORS_ORIGINS contains '*', the middleware must not allow arbitrary origins."""
        app = FastAPI()
        app.add_middleware(CSRFOriginMiddleware, allowed_origins=["*"])

        @app.post("/resource")
        def resource():
            return {"ok": True}

        c = TestClient(app, raise_server_exceptions=True)
        r = c.post("/resource", headers={"Origin": "http://evil.example.com"})
        assert r.status_code == 403

    def test_wildcard_in_allowlist_allows_no_origin(self):
        """No-origin requests (non-browser) still pass even with wildcard-only allowlist."""
        app = FastAPI()
        app.add_middleware(CSRFOriginMiddleware, allowed_origins=["*"])

        @app.post("/resource")
        def resource():
            return {"ok": True}

        c = TestClient(app, raise_server_exceptions=True)
        r = c.post("/resource")
        assert r.status_code == 200


class TestMiddlewareWiredIntoMainApp:
    """Verify CSRFOriginMiddleware is actually registered in the real app."""

    def test_csrf_middleware_present_in_main(self):
        import ast
        import os
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        assert "CSRFOriginMiddleware" in source, (
            "CSRFOriginMiddleware must be imported and registered in api/main.py"
        )
        assert "add_middleware(CSRFOriginMiddleware" in source, (
            "app.add_middleware(CSRFOriginMiddleware, ...) must appear in api/main.py"
        )
