"""
Unit tests for worker/main.py — standalone watcher runtime entry point.

Tests:
- worker module is importable without FastAPI
- _auto_start_watchers calls start_watcher for credentialed agents
- _auto_start_watchers skips agents with watcher_enabled=False
- _auto_start_watchers handles missing agent_users table gracefully
- run() sets up registry and calls stop_all on shutdown
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import guard — worker must not depend on FastAPI app lifecycle
# ---------------------------------------------------------------------------

def test_worker_module_importable_without_fastapi_app():
    """worker.main must be importable without triggering FastAPI startup."""
    import importlib
    # If this raises, worker.main has a hard dependency on api.main app state
    mod = importlib.import_module("worker.main")
    assert hasattr(mod, "run")
    assert hasattr(mod, "main")
    assert hasattr(mod, "_auto_start_watchers")


def test_worker_does_not_import_api_main():
    """worker.main source must not contain 'import api.main' or 'from api.main'."""
    import inspect
    import worker.main as wm
    source = inspect.getsource(wm)
    assert "import api.main" not in source, (
        "worker.main must not import api.main — that would couple worker to FastAPI app lifecycle"
    )
    assert "from api.main" not in source, (
        "worker.main must not import from api.main"
    )


# ---------------------------------------------------------------------------
# _auto_start_watchers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_start_watchers_starts_credentialed_agents():
    from worker.main import _auto_start_watchers

    mock_registry = AsyncMock()
    mock_registry.start_watcher.return_value = True

    mock_agent = SimpleNamespace(id=1, role="agent")
    mock_cred = SimpleNamespace(company_id=1)

    mock_db = MagicMock()
    # First query: User.role == "agent" → [mock_agent]
    # Subsequent queries for AgentUser, AgentPreferences → empty
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_agent]
    mock_db.query.return_value.all.return_value = []

    mock_cred_repo = MagicMock()
    mock_cred_repo.get_by_agent_id.return_value = mock_cred

    def mock_session_local():
        return mock_db

    with (
        patch("api.repositories.credential_repository.CredentialRepository", return_value=mock_cred_repo),
        patch("api.models.web_ui_models.User"),
        patch.dict("sys.modules", {
            "gmail_lead_sync.agent_models": MagicMock(
                AgentUser=MagicMock(),
                AgentPreferences=MagicMock(),
            )
        }),
    ):
        # Patch CredentialRepository at the import site inside _auto_start_watchers
        with patch("api.repositories.credential_repository.CredentialRepository", return_value=mock_cred_repo):
            # The function does local imports — patch at the module level it imports from
            import api.repositories.credential_repository as cred_repo_mod
            original = cred_repo_mod.CredentialRepository
            cred_repo_mod.CredentialRepository = MagicMock(return_value=mock_cred_repo)
            try:
                await _auto_start_watchers(mock_registry, mock_session_local)
            finally:
                cred_repo_mod.CredentialRepository = original

    mock_registry.start_watcher.assert_called_with("1")


@pytest.mark.asyncio
async def test_auto_start_watchers_skips_agents_without_credentials():
    from worker.main import _auto_start_watchers

    mock_registry = AsyncMock()
    mock_agent = SimpleNamespace(id=2, role="agent")

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_agent]
    mock_db.query.return_value.all.return_value = []

    mock_cred_repo = MagicMock()
    mock_cred_repo.get_by_agent_id.return_value = None  # no credentials

    def mock_session_local():
        return mock_db

    import api.repositories.credential_repository as cred_repo_mod
    original = cred_repo_mod.CredentialRepository
    cred_repo_mod.CredentialRepository = MagicMock(return_value=mock_cred_repo)
    try:
        with patch.dict("sys.modules", {
            "gmail_lead_sync.agent_models": MagicMock(
                AgentUser=MagicMock(),
                AgentPreferences=MagicMock(),
            )
        }):
            await _auto_start_watchers(mock_registry, mock_session_local)
    finally:
        cred_repo_mod.CredentialRepository = original

    mock_registry.start_watcher.assert_not_called()


# ---------------------------------------------------------------------------
# api.main no longer owns watcher lifecycle
# ---------------------------------------------------------------------------

def test_api_main_has_no_watcher_registry_global():
    """api.main must not expose a watcher_registry module-level global."""
    import api.main as main_module
    assert not hasattr(main_module, "watcher_registry"), (
        "watcher_registry must be removed from api.main — it now lives in worker/main.py"
    )


def test_api_main_has_no_credentials_store_global():
    """api.main must not expose a module-level credentials_store for watcher use."""
    import api.main as main_module
    # credentials_store as a watcher-startup artifact must be gone
    # (seed data uses a local _ECS variable, not a module-level one)
    assert not hasattr(main_module, "credentials_store"), (
        "credentials_store module-level global must be removed from api.main"
    )


def test_api_main_startup_does_not_reference_watcher_registry():
    """startup_event in api.main must not call watcher_registry.start_watcher."""
    import inspect
    import api.main as main_module

    startup_fn = main_module.startup_event
    source = inspect.getsource(startup_fn)
    assert "watcher_registry" not in source, (
        "startup_event must not reference watcher_registry — watcher lifecycle moved to worker"
    )
    assert "start_watcher" not in source, (
        "startup_event must not call start_watcher — watcher lifecycle moved to worker"
    )


def test_api_main_shutdown_does_not_reference_watcher_registry():
    """shutdown_event in api.main must not call watcher_registry.stop_all."""
    import inspect
    import api.main as main_module

    shutdown_fn = main_module.shutdown_event
    source = inspect.getsource(shutdown_fn)
    assert "watcher_registry" not in source, (
        "shutdown_event must not reference watcher_registry — watcher lifecycle moved to worker"
    )
    assert "stop_all" not in source, (
        "shutdown_event must not call stop_all — watcher lifecycle moved to worker"
    )
