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

## 6. Pydantic v2 — repo-owned v1-style cleanup (RESOLVED)

**Status: Resolved.** All v1-style Pydantic patterns in our own code have been migrated.

**Fixed:**
- `class Config: schema_extra` → `model_config = ConfigDict(json_schema_extra=...)` across all affected models
- `class Config: from_attributes = True` → `model_config = ConfigDict(from_attributes=True)` across all affected models
- `@validator` → `@field_validator` with `@classmethod` in all affected models and validators
- `allow_reuse=True` removed from all `validator(...)` calls

Files touched: `api/models/template_models.py`, `lead_source_models.py`, `agent_models.py`,
`audit_models.py`, `company_models.py`, `lead_models.py`, `settings_models.py`,
`api/routers/admin_auth.py`, `agent_onboarding.py`, `gmail_lead_sync/validation.py`,
`api/utils/validation.py`.

---

## 6a. Pydantic v2 — FastAPI/Pydantic compatibility noise (deferred)

**Status: Deferred — not in our code.**

**Problem:** 536 `Field(deprecated=...)` warnings are emitted by FastAPI 0.125.0
internally via `fastapi/_compat/v2.py` when building route parameter models. This is a
FastAPI/Pydantic version compatibility issue — FastAPI passes `deprecated=` as a keyword
argument to `pydantic.Field()`, which Pydantic v2 has deprecated in favour of
`json_schema_extra={'deprecated': True}`.

**Action:** Upgrade FastAPI when a version is available that resolves this internal
compatibility issue. No changes needed in our code.

---

## 6b. Pydantic v2 — `from_orm()` modernization in routers (deferred, low priority)

**Status: Deferred — works today, will break in Pydantic v3.**

**Problem:** Several routers still call `.from_orm(obj)` which is deprecated in Pydantic v2.
The v2 equivalent is `.model_validate(obj)`. The affected models already have
`from_attributes=True` set, so the behavior is identical.

**Files:**
- `api/routers/admin_lead_sources.py` — multiple `.from_orm(lead_source)` calls
- `api/routers/admin_templates.py` — multiple `.from_orm(template)` calls

**Action:** Replace `.from_orm(obj)` with `.model_validate(obj)` in the above routers.
Low-risk mechanical change. No behavior change since `from_attributes=True` is already set.

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
