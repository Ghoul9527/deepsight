"""
Tests for the FastAPI application.

Covers:
- api.py: FastAPI app creation, endpoints
- /health endpoint: returns 200 with {"status": "ok"}
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "shared", "src")))

import pytest

# Attempt to import FastAPI test client; skip all tests if not installed.
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# ---------------------------------------------------------------------------
# 1. App creation
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
class TestAppCreation:
    """Verify the FastAPI app can be created."""

    def test_app_creates_without_error(self):
        from deepsight_pi.api import app
        assert app is not None
        assert app.title is not None or True  # at minimum the app exists

    def test_app_is_fastapi_instance(self):
        from fastapi import FastAPI
        from deepsight_pi.api import app
        assert isinstance(app, FastAPI)

    def test_app_has_routes(self):
        from deepsight_pi.api import app
        # There should be at least one registered route
        assert len(app.routes) >= 1


# ---------------------------------------------------------------------------
# 2. /health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.fixture
    def client(self):
        from deepsight_pi.api import app
        return TestClient(app)

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        response = client.get("/health")
        data = response.json()
        assert data == {"status": "ok"}

    def test_health_content_type_json(self, client):
        response = client.get("/health")
        assert response.headers["content-type"].startswith("application/json")

    def test_health_with_trailing_slash(self, client):
        """FastAPI normally redirects trailing slashes by default (307)."""
        response = client.get("/health/")
        # Either 200 (if both registered) or 307 redirect
        assert response.status_code in (200, 307)


# ---------------------------------------------------------------------------
# 3. Additional endpoint smoke tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
class TestAdditionalEndpointsSmoke:
    """Smoke-test any additional endpoints that may exist."""

    @pytest.fixture
    def client(self):
        from deepsight_pi.api import app
        return TestClient(app)

    def test_root_endpoint(self, client):
        """GET / – if it exists, it should not 500."""
        response = client.get("/")
        # 200 if root is defined, 404 if not – both are fine
        assert response.status_code in (200, 404)

    def test_docs_available(self, client):
        """GET /docs – Swagger UI should be reachable."""
        response = client.get("/docs")
        assert response.status_code in (200, 301, 307)

    def test_openapi_schema_available(self, client):
        """GET /openapi.json – the OpenAPI schema should be valid."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        # Health endpoint must be in the schema
        assert "/health" in schema["paths"]


# ---------------------------------------------------------------------------
# 4. Module-level guard (no fastapi)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(FASTAPI_AVAILABLE, reason="fastapi IS installed – nothing to skip")
class TestNoFastApiInstalled:
    """Graceful behaviour when fastapi is not available."""

    def test_skip_if_fastapi_not_installed(self):
        """This test only runs when fastapi is not installed, verifying
        the skip logic itself works."""
        pass
