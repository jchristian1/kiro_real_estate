# Follow-up Items

Tracked cleanup tasks that were intentionally deferred from the production-hardening pass.
Each item should be addressed in a dedicated PR, not mixed into unrelated work.

---

## 1. Remove `gmail_lead_sync/health.py` (legacy dead code)

**File:** `gmail_lead_sync/health.py`

**Problem:** Imports Flask and defines a Flask app, but is not imported anywhere in the
current runtime (`api/`, `worker/`). Flask is not in `requirements.txt`. This file
confuses future dependency audits because it makes Flask appear as a runtime dependency
when it is not.

**Action:** Delete the file. Confirm `flask` does not need to be added to any requirements
file. Update any references if found.

---

## 2. Fix `tests/unit/test_watcher_coordination.py` (pre-existing test failures)

**File:** `tests/unit/test_watcher_coordination.py`

**Problem:** 5 tests in `TestWorkerReconciliation` fail with:
`TypeError: _reconcile_sync() missing 1 required positional argument: 'loop'`

The test signatures do not match the current `worker/main.py` implementation of
`_reconcile_sync(registry, SessionLocal, loop)`. These failures predate the
production-hardening branch and were not caused by it.

**Action:** Update the test fixtures to pass the `loop` argument, or refactor
`_reconcile_sync` to not require it as a positional argument.

---

## 3. Evaluate legacy `gmail-lead-sync` CLI entry point

**File:** `gmail_lead_sync/__main__.py`, `pyproject.toml` `[project.scripts]`

**Problem:** The `gmail-lead-sync` CLI entry point is registered in `pyproject.toml` as
a backward-compatibility alias but is not used in any current deployment path (Docker,
systemd, or bare local dev). It describes a legacy single-process architecture.

**Action:** Evaluate whether to remove the entry point and `__main__.py`, or add an
explicit deprecation notice. If removed, update `pyproject.toml` and any docs that
reference the CLI.

---

## 4. Expand `pyproject.toml` package discovery (if packaging is ever formalized)

**File:** `pyproject.toml` `[tool.setuptools.packages.find]`

**Problem:** `include = ["gmail_lead_sync*"]` only discovers the `gmail_lead_sync`
package. `api/` and `worker/` are Python packages (have `__init__.py`) but are excluded.
This is acceptable while `pip install .` is not the canonical runtime path, but would
need to change if the packaging story is ever formalized.

**Action:** If `pip install .` ever becomes a supported install path, expand
`packages.find` to include `api` and `worker`, and update the Dockerfile to use
`pip install .` instead of `pip install -r requirements.txt`.

---

## 6. Pydantic v2 config/schema deprecation warnings — partially resolved

**Status:** The warnings from our own code have been fixed. One warning source remains
that is outside our control.

**Fixed in this pass:**
- `api/models/template_models.py` — `class Config: schema_extra` → `model_config = ConfigDict(json_schema_extra=...)`, `@validator` → `@field_validator`
- `api/models/lead_source_models.py` — `class Config` → `model_config`, `@validator` → `@field_validator`
- `api/models/agent_models.py` — `class Config` → `model_config`, `@validator` + `allow_reuse` → `@field_validator`
- `api/models/audit_models.py`, `company_models.py`, `lead_models.py`, `settings_models.py` — `class Config` → `model_config`
- `api/routers/admin_auth.py`, `agent_onboarding.py` — `class Config` → `model_config`
- `gmail_lead_sync/validation.py` — `@validator` → `@field_validator`
- `api/utils/validation.py` — removed `allow_reuse=True` from docstring example

**Remaining warning (not in our code):**
The `Field(deprecated=...)` warning (536x) is emitted by FastAPI 0.125.0 internally
when building route parameter models. It comes from `fastapi/_compat/v2.py` calling
`pydantic.Field(deprecated=...)` — a FastAPI/Pydantic version compatibility issue.
This cannot be fixed by changing our models. It will resolve when FastAPI releases
a version that uses `json_schema_extra={'deprecated': True}` instead.

**Action:** Upgrade FastAPI when a version is available that resolves this internal
compatibility issue. No action needed in our code.

---

## 7. Move `fast-check` to `devDependencies` in `frontend/package.json`

**File:** `frontend/package.json`

**Problem:** `fast-check` (a property-based testing library) is listed under
`dependencies` (production) rather than `devDependencies`. It is a test tool and
should not be bundled into the production frontend build.

**Action:** Move `fast-check` from `dependencies` to `devDependencies` in
`frontend/package.json`. Verify the frontend build and tests still pass.

---

## 8. Rename `SESSION_EXPIRY_HOURS` in `api/auth.py` to clarify it is a fallback default

**File:** `api/auth.py`

**Context:** After the session-timeout config fix, `SESSION_EXPIRY_HOURS = 24` remains as
the default parameter value for `create_session()` and `set_session_cookie()`. The constant
is no longer the primary source of truth — `config.session_timeout_hours` is — but the name
does not make that clear.

**Action:** Rename `SESSION_EXPIRY_HOURS` to `_DEFAULT_SESSION_EXPIRY_HOURS` (or similar)
to signal it is a fallback default, not the authoritative value. Update the two function
signatures and any tests that import the constant by name. This is a cosmetic/clarity change
with no behavioral impact.
