# Contributing

## Running Tests

```bash
# Full suite (unit + integration + property-based)
make test

# Subsets
pytest tests/unit/          # unit tests only
pytest tests/integration/   # integration tests only
pytest tests/property/      # property-based tests only (Hypothesis)

# With coverage report
pytest tests/ --cov=api --cov=gmail_lead_sync --cov-report=html
```

All tests must pass before opening a PR. The CI pipeline runs `make test` on every push.

## Adding a New API Endpoint

The backend follows a strict 4-layer pattern: **router → service → repository → model**. Add one layer at a time, bottom-up.

### 1. Model (if new data shape is needed)

Add a Pydantic request/response model in `api/models/`:

```python
# api/models/widget_models.py
from pydantic import BaseModel

class WidgetCreate(BaseModel):
    name: str
    value: int

class WidgetResponse(BaseModel):
    id: int
    name: str
    value: int
```

### 2. Repository (data access)

Add a repository class in `api/repositories/`. All DB queries live here — never in routers or services.

```python
# api/repositories/widget_repository.py
from sqlalchemy.orm import Session
from gmail_lead_sync.models import Widget  # your SQLAlchemy model

class WidgetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, widget_id: int, agent_id: str):
        return (
            self.db.query(Widget)
            .filter(Widget.id == widget_id, Widget.agent_id == agent_id)
            .first()
        )

    def create(self, name: str, value: int, agent_id: str) -> Widget:
        widget = Widget(name=name, value=value, agent_id=agent_id)
        self.db.add(widget)
        self.db.commit()
        self.db.refresh(widget)
        return widget
```

Always include a `tenant_id` / `agent_id` filter on every tenant-scoped query.

### 3. Service (business logic, optional)

If the endpoint needs business logic beyond a simple CRUD operation, add a service in `api/services/`. Services must not import FastAPI types (`Request`, `Response`, `Depends`).

### 4. Router

Add the route in `api/routers/`. Use the naming convention:
- `admin_*.py` — platform-admin endpoints (role: `platform_admin`)
- `agent_*.py` — agent-app endpoints (role: `agent`)
- `public_*.py` — unauthenticated endpoints

```python
# api/routers/agent_widgets.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.dependencies.auth import get_current_agent
from api.dependencies.db import get_db
from api.models.widget_models import WidgetCreate, WidgetResponse
from api.repositories.widget_repository import WidgetRepository

router = APIRouter(prefix="/api/v1/agent/widgets", tags=["agent-widgets"])

@router.post("/", response_model=WidgetResponse, status_code=201)
def create_widget(
    body: WidgetCreate,
    agent=Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    return repo.create(body.name, body.value, agent_id=str(agent.id))
```

### 5. Register the router

Add the router to `api/main.py`:

```python
from api.routers.agent_widgets import router as agent_widgets_router
app.include_router(agent_widgets_router)
```

### 6. Write tests

Add unit tests in `tests/unit/test_agent_widgets.py` covering the happy path and error cases (404, 403 cross-tenant). See existing tests for the `TestClient` + in-memory DB fixture pattern.

---

## Adding a New Frontend Page

### 1. Decide which app the page belongs to

- Agent-facing → `frontend/src/apps/agent/pages/`
- Platform-admin → `frontend/src/apps/platform-admin/pages/`
- Shared UI components → `frontend/src/shared/components/`

### 2. Create the page component

```tsx
// frontend/src/apps/agent/pages/WidgetsPage.tsx
import { useEffect, useState } from 'react'
import { apiClient } from '../../../shared/api/client'

export default function WidgetsPage() {
  const [widgets, setWidgets] = useState([])

  useEffect(() => {
    apiClient.get('/api/v1/agent/widgets').then(setWidgets)
  }, [])

  return <div>{/* render widgets */}</div>
}
```

### 3. Add the route

Open the app's root component and add a `<Route>`:

```tsx
// frontend/src/apps/agent/AgentApp.tsx
import WidgetsPage from './pages/WidgetsPage'

// Inside your <Routes>:
<Route path="widgets" element={<WidgetsPage />} />
```

### 4. Add navigation link (if applicable)

Add a link in the sidebar or nav component for the relevant app.

### 5. Verify the build

```bash
make build   # must exit 0 with no TypeScript errors
```

---

## Branching and PR Process

### Branch naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<short-description>` | `feat/widget-endpoint` |
| Bug fix | `fix/<short-description>` | `fix/lead-tenant-scoping` |
| Chore / docs | `chore/<short-description>` | `chore/update-readme` |

### Workflow

1. Branch off `main`: `git checkout -b feat/my-feature`
2. Make changes in small, focused commits.
3. Ensure `make lint`, `make typecheck`, and `make test` all pass locally.
4. Push and open a PR against `main`.
5. The CI pipeline runs automatically — the PR cannot be merged until CI is green.
6. Request at least one review.
7. Squash-merge once approved.

### Commit messages

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
feat: add widget endpoint
fix: scope lead queries to agent_id
docs: update architecture diagram
chore: bump ruff to 0.4
```

### What CI checks

- `make lint` — ruff (Python) + eslint (TypeScript)
- `make typecheck` — mypy (Python) + tsc (TypeScript)
- `make test` — full pytest suite

Fix any failures before requesting review.
