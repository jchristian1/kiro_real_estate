"""
Property-based tests for .env.example coverage.

Feature: production-hardening

# Feature: production-hardening, Property 2: .env.example covers all config variables

**Property 2: .env.example covers all config variables** — for any environment
variable referenced in ``api/config.py``'s ``load_config()`` function, that
variable name SHALL appear in the root-level ``.env.example`` file.

**Validates: Requirements 1.3, 4.2**
"""

import ast
import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers — static analysis of load_config()
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_FILE = _REPO_ROOT / "api" / "config.py"
_ENV_EXAMPLE_FILE = _REPO_ROOT / ".env.example"


def _extract_env_vars_from_config() -> list[str]:
    """
    Parse ``api/config.py`` with the AST and return every variable name passed
    as the first argument to ``os.getenv(...)`` or ``os.environ.get(...)``
    calls that appear inside the ``load_config`` function body.
    """
    source = _CONFIG_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CONFIG_FILE))

    # Locate the load_config function node
    load_config_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "load_config":
            load_config_node = node
            break

    if load_config_node is None:
        raise RuntimeError("Could not find load_config() in api/config.py")

    var_names: list[str] = []

    for node in ast.walk(load_config_node):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        # Match os.getenv("VAR_NAME", ...) and os.environ.get("VAR_NAME", ...)
        is_os_getenv = (
            isinstance(func, ast.Attribute)
            and func.attr == "getenv"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        )
        is_os_environ_get = (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        )

        if (is_os_getenv or is_os_environ_get) and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                var_names.append(first_arg.value)

    return var_names


def _extract_var_names_from_env_example() -> set[str]:
    """
    Read ``.env.example`` and return the set of variable names defined there.
    A variable name is any ``KEY=...`` line where KEY matches ``[A-Z0-9_]+``.
    """
    content = _ENV_EXAMPLE_FILE.read_text(encoding="utf-8")
    names: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        # Skip blank lines and comment lines
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z0-9_]+)\s*=", stripped)
        if match:
            names.add(match.group(1))
    return names


# ---------------------------------------------------------------------------
# Pre-compute once at module load (deterministic — no randomness needed)
# ---------------------------------------------------------------------------

_CONFIG_VARS: list[str] = _extract_env_vars_from_config()
_ENV_EXAMPLE_VARS: set[str] = _extract_var_names_from_env_example()


# ---------------------------------------------------------------------------
# Property 2: .env.example covers all config variables
# ---------------------------------------------------------------------------


class TestProperty2EnvExampleCoversAllConfigVariables:
    """
    Property 2: every environment variable consumed by load_config() in
    api/config.py MUST appear in the root-level .env.example file.
    """

    @given(var_name=st.sampled_from(_CONFIG_VARS))
    @settings(max_examples=1)
    def test_each_config_var_appears_in_env_example(self, var_name: str):
        """
        For each variable name found in load_config(), assert it is documented
        in .env.example.

        # Feature: production-hardening, Property 2: .env.example covers all config variables
        """
        assert var_name in _ENV_EXAMPLE_VARS, (
            f"Variable '{var_name}' is referenced in api/config.py load_config() "
            f"but is missing from .env.example. "
            f"Add it with an inline comment explaining its purpose."
        )

    def test_env_example_file_exists(self):
        """
        The root-level .env.example file must exist.
        """
        assert _ENV_EXAMPLE_FILE.exists(), (
            f".env.example not found at {_ENV_EXAMPLE_FILE}. "
            "Create it with all required environment variables documented."
        )

    def test_config_file_exists(self):
        """
        api/config.py must exist and contain a load_config() function.
        """
        assert _CONFIG_FILE.exists(), f"api/config.py not found at {_CONFIG_FILE}"
        assert _CONFIG_VARS, (
            "No os.getenv() / os.environ.get() calls found inside load_config(). "
            "Check that api/config.py has not been restructured."
        )

    def test_all_config_vars_covered_exhaustive(self):
        """
        Exhaustive (non-Hypothesis) check: every variable in load_config() is
        in .env.example. Reports ALL missing variables at once.

        # Feature: production-hardening, Property 2: .env.example covers all config variables
        """
        missing = [v for v in _CONFIG_VARS if v not in _ENV_EXAMPLE_VARS]
        assert not missing, (
            "The following variables are used in load_config() but missing from "
            ".env.example:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )
