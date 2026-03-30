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

## 5. Move `fast-check` to `devDependencies` in `frontend/package.json`

**File:** `frontend/package.json`

**Problem:** `fast-check` (a property-based testing library) is listed under
`dependencies` (production) rather than `devDependencies`. It is a test tool and
should not be bundled into the production frontend build.

**Action:** Move `fast-check` from `dependencies` to `devDependencies` in
`frontend/package.json`. Verify the frontend build and tests still pass.
