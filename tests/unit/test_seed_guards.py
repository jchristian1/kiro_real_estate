"""
Focused tests for seed_data.py environment guards and startup seeding removal.

Verifies:
1. Seed script refuses to run when ENVIRONMENT != 'development'
2. Seed script refuses to run when DEV_SEED != 'true'
3. Seed script refuses to run when DEV_ADMIN_PASSWORD is missing
4. App startup_event() does NOT create any users
5. seed_users() creates admin with the supplied password (not a hardcoded one)
6. No credentials are printed to structured logs
"""

import os
import sys
import importlib
import subprocess
import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed_data.py")


def run_seed(env_overrides: dict) -> subprocess.CompletedProcess:
    """Run seed_data.py as a subprocess with the given env overrides."""
    env = {k: v for k, v in os.environ.items()}
    # Strip any inherited seed vars so tests are hermetic
    for key in ("ENVIRONMENT", "DEV_SEED", "DEV_ADMIN_PASSWORD", "DEV_VIEWER_PASSWORD"):
        env.pop(key, None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# 1. ENVIRONMENT guard
# ---------------------------------------------------------------------------

class TestEnvironmentGuard:
    def test_unset_environment_exits_nonzero(self):
        result = run_seed({"DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert result.returncode != 0, "Should exit non-zero when ENVIRONMENT is unset"

    def test_unset_environment_prints_clear_message(self):
        result = run_seed({"DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "Seeding is only allowed in development environments" in result.stdout

    def test_staging_environment_exits_nonzero(self):
        result = run_seed({"ENVIRONMENT": "staging", "DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert result.returncode != 0

    def test_staging_environment_prints_clear_message(self):
        result = run_seed({"ENVIRONMENT": "staging", "DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "Seeding is only allowed in development environments" in result.stdout
        assert "staging" in result.stdout  # shows the actual value

    def test_production_environment_exits_nonzero(self):
        result = run_seed({"ENVIRONMENT": "production", "DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert result.returncode != 0

    def test_production_environment_prints_clear_message(self):
        result = run_seed({"ENVIRONMENT": "production", "DEV_SEED": "true", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "Seeding is only allowed in development environments" in result.stdout


# ---------------------------------------------------------------------------
# 2. DEV_SEED guard
# ---------------------------------------------------------------------------

class TestDevSeedGuard:
    def test_unset_dev_seed_exits_nonzero(self):
        result = run_seed({"ENVIRONMENT": "development", "DEV_ADMIN_PASSWORD": "testpass"})
        assert result.returncode != 0

    def test_unset_dev_seed_prints_clear_message(self):
        result = run_seed({"ENVIRONMENT": "development", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "DEV_SEED is not set to 'true'" in result.stdout

    def test_false_dev_seed_exits_nonzero(self):
        result = run_seed({"ENVIRONMENT": "development", "DEV_SEED": "false", "DEV_ADMIN_PASSWORD": "testpass"})
        assert result.returncode != 0

    def test_false_dev_seed_prints_clear_message(self):
        result = run_seed({"ENVIRONMENT": "development", "DEV_SEED": "false", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "DEV_SEED is not set to 'true'" in result.stdout

    def test_dev_seed_message_mentions_make_seed_dev(self):
        result = run_seed({"ENVIRONMENT": "development", "DEV_SEED": "false", "DEV_ADMIN_PASSWORD": "testpass"})
        assert "make seed-dev" in result.stdout


# ---------------------------------------------------------------------------
# 3. DEV_ADMIN_PASSWORD guard (unit — mock DB to isolate the check)
# ---------------------------------------------------------------------------

class TestAdminPasswordGuard:
    def test_missing_password_exits_nonzero(self, monkeypatch):
        """seed_users() must exit(1) when DEV_ADMIN_PASSWORD is not set."""
        # Import fresh with monkeypatched env
        monkeypatch.delenv("DEV_ADMIN_PASSWORD", raising=False)

        # Import the module under test
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        import scripts.seed_data as sd
        importlib.reload(sd)

        mock_db = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            sd.seed_users(mock_db)
        assert exc_info.value.code != 0

    def test_missing_password_message(self, monkeypatch, capsys):
        """seed_users() must print a clear error when DEV_ADMIN_PASSWORD is missing."""
        monkeypatch.delenv("DEV_ADMIN_PASSWORD", raising=False)

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        import scripts.seed_data as sd
        importlib.reload(sd)

        mock_db = MagicMock()
        with pytest.raises(SystemExit):
            sd.seed_users(mock_db)

        captured = capsys.readouterr()
        assert "DEV_ADMIN_PASSWORD" in captured.out


# ---------------------------------------------------------------------------
# 4. App startup does NOT create users
# ---------------------------------------------------------------------------

class TestStartupNoSeeding:
    def test_startup_event_does_not_call_seed_users(self):
        """startup_event() must not import or call any seed function."""
        # Read the startup_event source and assert seed calls are absent
        import ast
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        tree = ast.parse(source)

        # Find the startup_event function body
        startup_body_source = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "startup_event":
                startup_body_source = ast.unparse(node)
                break

        assert startup_body_source is not None, "startup_event not found in main.py"

        # None of these should appear in the startup body
        forbidden = ["seed_users", "seed_data", "seed_templates", "seed_leads",
                     "admin123", "admin/admin123"]
        for term in forbidden:
            assert term not in startup_body_source, (
                f"startup_event() must not reference '{term}' — found in main.py"
            )

    def test_startup_event_does_not_query_user_count(self):
        """startup_event() must not check user count to decide whether to seed."""
        import ast
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        tree = ast.parse(source)
        startup_body_source = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "startup_event":
                startup_body_source = ast.unparse(node)
                break

        assert startup_body_source is not None
        assert ".count() == 0" not in startup_body_source, (
            "startup_event() must not check user count — this is the auto-seed trigger pattern"
        )


# ---------------------------------------------------------------------------
# 5. seed_users() uses supplied password, not a hardcoded one
# ---------------------------------------------------------------------------

class TestSeedUsersUsesSuppliedPassword:
    def test_admin_password_comes_from_env(self, monkeypatch):
        """seed_users() must hash DEV_ADMIN_PASSWORD, not a hardcoded string."""
        monkeypatch.setenv("DEV_ADMIN_PASSWORD", "supplied-password-xyz")

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        import scripts.seed_data as sd
        importlib.reload(sd)

        captured_hash_input = []

        def mock_hash(password):
            captured_hash_input.append(password)
            return "hashed"

        # Mock DB that returns None (user doesn't exist yet)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query

        with patch("scripts.seed_data.hash_password", side_effect=mock_hash):
            with patch.object(mock_db, "add"), patch.object(mock_db, "commit"), \
                 patch.object(mock_db, "refresh"):
                sd.seed_users(mock_db)

        assert "supplied-password-xyz" in captured_hash_input, (
            "seed_users() must hash the value from DEV_ADMIN_PASSWORD"
        )
        assert "admin123" not in captured_hash_input, (
            "seed_users() must never hash the hardcoded 'admin123' password"
        )

    def test_no_hardcoded_admin123_in_seed_script(self):
        """Verify admin123 does not appear anywhere in seed_data.py source."""
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "seed_data.py"
        )
        with open(seed_path) as f:
            source = f.read()
        assert "admin123" not in source, "admin123 must not appear in seed_data.py"
        assert "viewer123" not in source, "viewer123 must not appear in seed_data.py"


# ---------------------------------------------------------------------------
# 6. No credentials in structured logs
# ---------------------------------------------------------------------------

class TestNoCredentialsInLogs:
    def test_startup_log_does_not_contain_credentials(self):
        """startup_event() log calls must not contain credential strings."""
        import ast
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "api", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        forbidden_in_logs = ["admin123", "viewer123", "admin/admin123",
                             "login: admin", "password=admin"]
        for term in forbidden_in_logs:
            assert term not in source, (
                f"main.py must not contain '{term}' — credential in log or source"
            )

    def test_seed_summary_does_not_print_password(self, monkeypatch, capsys):
        """seed_users() output must not contain the actual password value."""
        test_password = "super-secret-verify-99"
        monkeypatch.setenv("DEV_ADMIN_PASSWORD", test_password)

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        import scripts.seed_data as sd
        importlib.reload(sd)

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value = mock_query

        with patch("scripts.seed_data.hash_password", return_value="hashed"), \
             patch.object(mock_db, "add"), patch.object(mock_db, "commit"), \
             patch.object(mock_db, "refresh"):
            sd.seed_users(mock_db)

        captured = capsys.readouterr()
        assert test_password not in captured.out, (
            "seed_users() must not print the actual password to stdout"
        )


# ---------------------------------------------------------------------------
# 7. Docker entrypoint does not call seed_data.py
# ---------------------------------------------------------------------------

class TestDockerEntrypointNoSeed:
    def test_entrypoint_does_not_invoke_seed_script(self):
        """docker-entrypoint.sh must not call seed_data.py."""
        entrypoint_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docker-entrypoint.sh"
        )
        with open(entrypoint_path) as f:
            content = f.read()

        assert "seed_data.py" not in content, (
            "docker-entrypoint.sh must not call seed_data.py — seeding must be explicit"
        )
        assert "seed_data" not in content, (
            "docker-entrypoint.sh must not reference seed_data in any form"
        )


# ---------------------------------------------------------------------------
# 8. Documentation consistency — no hardcoded credentials in docs
# ---------------------------------------------------------------------------

class TestDocumentationConsistency:
    DOC_FILES = [
        "README.md",
        "SECURITY.md",
        "docs/FIRST_START.md",
        "docs/API.md",
        "scripts/README.md",
    ]

    def _read(self, filename):
        path = os.path.join(os.path.dirname(__file__), "..", "..", filename)
        with open(path) as f:
            return f.read()

    @pytest.mark.parametrize("filename", DOC_FILES)
    def test_no_admin123_in_docs(self, filename):
        content = self._read(filename)
        assert "admin123" not in content, f"{filename} must not contain 'admin123'"

    @pytest.mark.parametrize("filename", DOC_FILES)
    def test_no_viewer123_in_docs(self, filename):
        content = self._read(filename)
        assert "viewer123" not in content, f"{filename} must not contain 'viewer123'"

    @pytest.mark.parametrize("filename", DOC_FILES)
    def test_no_auto_seeds_on_startup_claim(self, filename):
        content = self._read(filename)
        assert "auto-seeds on first startup" not in content, (
            f"{filename} must not claim the API auto-seeds on startup"
        )
