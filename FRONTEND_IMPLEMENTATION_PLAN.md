# Frontend Implementation Plan

**Project**: Gmail Lead Sync Web UI & API Layer  
**Phase**: Frontend Implementation (Tasks 15-27)  
**Technology Stack**: React + TypeScript + Vite + Tailwind CSS  
**Date**: March 3, 2026

---

## Executive Summary

This document outlines the implementation strategy for the React-based frontend of the Gmail Lead Sync Web UI. The frontend will provide a modern, responsive interface for managing agents, lead sources, templates, and monitoring system health.

### Goals
1. **User-Friendly Interface**: Intuitive UI for all management operations
2. **Real-Time Updates**: Live status monitoring for watchers and system health
3. **Form Validation**: Client-side validation with clear error messages
4. **Responsive Design**: Mobile-friendly layouts using Tailwind CSS
5. **Type Safety**: Full TypeScript coverage for maintainability
6. **Testing**: Comprehensive unit and integration tests

---

## Technology Stack

### Core Framework
- **React 18+**: Component-based UI library
- **TypeScript**: Type-safe JavaScript
- **Vite**: Fast build tool and dev server

### Routing & State
- **React Router 6+**: Client-side routing with protected routes
- **React Context + Hooks**: State management (no Redux needed)

### UI & Styling
- **Tailwind CSS**: Utility-first CSS framework
- **Headless UI**: Unstyled, accessible UI components
- **Heroicons**: Icon library

### Forms & Validation
- **React Hook Form**: Performant form management
- **Zod**: TypeScript-first schema validation

### HTTP & API
- **Axios**: HTTP client with interceptors
- **React Query** (optional): Server state management

### Testing
- **Vitest**: Unit testing framework
- **React Testing Library**: Component testing
- **MSW** (Mock Service Worker): API mocking

---

## Architecture Overview

### Directory Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── common/         # Generic components (Button, Input, Modal, etc.)
│   │   ├── forms/          # Form components (AgentForm, TemplateEditor, etc.)
│   │   ├── tables/         # Table components (LeadTable, AuditLogTable, etc.)
│   │   └── layout/         # Layout components (Header, Sidebar, etc.)
│   ├── contexts/           # React contexts
│   │   ├── AuthContext.tsx
│   │   └── ToastContext.tsx
│   ├── pages/              # Page components
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── AgentsPage.tsx
│   │   ├── LeadSourcesPage.tsx
│   │   ├── TemplatesPage.tsx
│   │   ├── LeadsPage.tsx
│   │   ├── AuditLogsPage.tsx
│   │   └── SettingsPage.tsx
│   ├── hooks/              # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useApi.ts
│   │   └── usePolling.ts
│   ├── services/           # API service layer
│   │   ├── api.ts          # Axios instance and interceptors
│   │   ├── authService.ts
│   │   ├── agentService.ts
│   │   ├── leadSourceService.ts
│   │   ├── templateService.ts
│   │   ├── watcherService.ts
│   │   ├── leadService.ts
│   │   └── settingsService.ts
│   ├── types/              # TypeScript type definitions
│   │   ├── api.ts
│   │   ├── models.ts
│   │   └── forms.ts
│   ├── utils/              # Utility functions
│   │   ├── validation.ts
│   │   ├── formatting.ts
│   │   └── constants.ts
│   ├── App.tsx             # Root component
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles
├── public/                 # Static assets
├── tests/                  # Test files
│   ├── unit/
│   └── integration/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

### Component Hierarchy

```
App
├── AuthProvider
│   ├── ToastProvider
│   │   ├── Router
│   │   │   ├── LoginPage
│   │   │   └── DashboardLayout
│   │   │       ├── Header
│   │   │       ├── Sidebar
│   │   │       └── Outlet (Page Content)
│   │   │           ├── DashboardPage
│   │   │           ├── AgentsPage
│   │   │           ├── LeadSourcesPage
│   │   │           ├── TemplatesPage
│   │   │           ├── LeadsPage
│   │   │           ├── AuditLogsPage
│   │   │           └── SettingsPage
```

---

## Implementation Strategy

### Phase 1: Foundation (Tasks 15)
**Goal**: Set up authentication, routing, and layout structure

#### Components to Build
1. **AuthContext** - Authentication state management
2. **LoginPage** - User login form
3. **DashboardLayout** - Main layout with sidebar and header
4. **ProtectedRoute** - Route guard for authenticated routes
5. **API Service Layer** - Axios configuration with interceptors

#### Key Features
- Session-based authentication
- Automatic token refresh
- Redirect on auth errors
- Protected route guards

#### Estimated Effort: 1-2 days

---

### Phase 2: Dashboard & Monitoring (Task 16)
**Goal**: Display system health and watcher status

#### Components to Build
1. **DashboardPage** - Main dashboard view
2. **HealthMetrics** - System health display
3. **WatcherStatusGrid** - Real-time watcher status
4. **RecentErrorsTable** - Error log display
5. **usePolling** hook - Auto-refresh data

#### Key Features
- Real-time health monitoring (5-second polling)
- Watcher status indicators
- Error log display
- System metrics visualization

#### Estimated Effort: 1 day

---

### Phase 3: Agent Management (Task 17)
**Goal**: CRUD operations for agents

#### Components to Build
1. **AgentsPage** - Agent list and management
2. **AgentList** - Table of agents with actions
3. **AgentForm** - Create/edit agent form
4. **AgentDetail** - Agent details view
5. **ConfirmDialog** - Confirmation modal for deletions
6. **WatcherControls** - Start/stop/sync buttons

#### Key Features
- Agent CRUD operations
- Email validation
- Credential encryption (handled by API)
- Watcher control integration
- Confirmation dialogs for dangerous actions

#### Estimated Effort: 2 days

---

### Phase 4: Lead Source Management (Task 18)
**Goal**: Manage lead sources with regex testing

#### Components to Build
1. **LeadSourcesPage** - Lead source list
2. **LeadSourceList** - Table of lead sources
3. **LeadSourceForm** - Create/edit form
4. **RegexTestHarness** - Interactive regex tester
5. **VersionHistory** - Version history display
6. **ConfirmDialog** - Deletion confirmation

#### Key Features
- Lead source CRUD operations
- Real-time regex testing
- Match highlighting
- Captured groups display
- Version history and rollback
- Timeout error handling

#### Estimated Effort: 2-3 days

---

### Phase 5: Template Management (Task 19)
**Goal**: Create and manage email templates

#### Components to Build
1. **TemplatesPage** - Template list
2. **TemplateList** - Table of templates
3. **TemplateEditor** - Rich template editor
4. **TemplatePreview** - Live preview with sample data
5. **PlaceholderButtons** - Insert placeholder buttons
6. **VersionHistory** - Version history sidebar
7. **ConfirmDialog** - Deletion confirmation

#### Key Features
- Template CRUD operations
- Placeholder insertion
- Real-time preview
- Validation (header injection, placeholders)
- Version history and rollback
- Sample data substitution

#### Estimated Effort: 2-3 days

---

### Phase 6: Watcher Control (Task 20)
**Goal**: Real-time watcher management

#### Components to Build
1. **WatcherStatusDisplay** - Status indicators
2. **WatcherControls** - Control buttons
3. **ConfirmDialog** - Stop confirmation
4. **usePolling** hook - Status updates

#### Key Features
- Real-time status updates (5-second polling)
- Start/stop/sync controls
- Last sync timestamp display
- Heartbeat monitoring
- Confirmation for stop action

#### Estimated Effort: 1 day

---

### Phase 7: Lead Viewing & Export (Task 21)
**Goal**: View and export leads

#### Components to Build
1. **LeadsPage** - Lead list and filters
2. **LeadTable** - Sortable lead table
3. **LeadFilters** - Filter controls
4. **LeadDetail** - Lead detail modal
5. **ExportButton** - CSV export trigger
6. **Pagination** - Pagination controls

#### Key Features
- Paginated lead list
- Sortable columns
- Filtering (agent, date range, status)
- Lead detail view
- CSV export with filters
- Success toast on export

#### Estimated Effort: 2 days

---

### Phase 8: Audit Logs & Settings (Task 22)
**Goal**: View audit logs and manage settings

#### Components to Build
1. **AuditLogsPage** - Audit log viewer
2. **AuditLogTable** - Filterable log table
3. **AuditLogFilters** - Filter controls
4. **SettingsPage** - Settings management
5. **SettingsForm** - Settings form with validation

#### Key Features
- Audit log viewing with pagination
- Filtering (action, user, date range)
- Settings CRUD operations
- Validation of setting values
- Success/error feedback

#### Estimated Effort: 1-2 days

---

### Phase 9: Toast Notifications & Error Handling (Task 23)
**Goal**: User feedback and error handling

#### Components to Build
1. **ToastContainer** - Toast notification system
2. **Toast** - Individual toast component
3. **ToastContext** - Toast state management
4. **ErrorBoundary** - Error boundary component
5. **useToast** hook - Toast management hook

#### Key Features
- Success toasts (auto-dismiss after 3 seconds)
- Error toasts (manual dismissal)
- User-friendly error messages
- Link to detailed error logs
- Consistent positioning

#### Estimated Effort: 1 day

---

### Phase 10: Testing & Polish (Task 24)
**Goal**: Comprehensive testing and UI polish

#### Testing Strategy
1. **Unit Tests** - Component logic and utilities
2. **Integration Tests** - User flows and API integration
3. **E2E Tests** (optional) - Full user scenarios

#### Key Areas
- Authentication flow
- Form validation
- API error handling
- Real-time updates
- Confirmation dialogs

#### Estimated Effort: 2-3 days

---

## Detailed Component Specifications

### 1. AuthContext

**Purpose**: Manage authentication state globally

**State**:
```typescript
interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}
```

**Methods**:
- `login(username: string, password: string): Promise<void>`
- `logout(): Promise<void>`
- `checkAuth(): Promise<void>`

**Features**:
- Session persistence
- Automatic auth check on mount
- Redirect on auth errors
- Loading states

---

### 2. API Service Layer

**Purpose**: Centralized API communication

**Structure**:
```typescript
// api.ts
const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
});

// Request interceptor
api.interceptors.request.use(config => {
  // Add any headers
  return config;
});

// Response interceptor
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Redirect to login
    }
    return Promise.reject(error);
  }
);
```

**Service Files**:
- `authService.ts` - Authentication operations
- `agentService.ts` - Agent CRUD
- `leadSourceService.ts` - Lead source CRUD
- `templateService.ts` - Template CRUD
- `watcherService.ts` - Watcher control
- `leadService.ts` - Lead viewing and export
- `settingsService.ts` - Settings management

---

### 3. Form Components

**Common Pattern**:
```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  field: z.string().min(1, 'Required'),
});

type FormData = z.infer<typeof schema>;

function MyForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    // API call
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Form fields */}
    </form>
  );
}
```

---

### 4. Real-Time Updates

**Polling Hook**:
```typescript
function usePolling<T>(
  fetchFn: () => Promise<T>,
  interval: number = 5000
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const result = await fetchFn();
        setData(result);
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    };

    fetch();
    const intervalId = setInterval(fetch, interval);

    return () => clearInterval(intervalId);
  }, [fetchFn, interval]);

  return { data, loading, error };
}
```

---

## TypeScript Type Definitions

### API Types

```typescript
// types/models.ts

export interface User {
  id: number;
  username: string;
  role: string;
  created_at: string;
}

export interface Agent {
  agent_id: string;
  email: string;
  created_at: string;
}

export interface LeadSource {
  id: number;
  sender_email: string;
  identifier_snippet: string;
  name_regex: string;
  phone_regex: string;
  template_id: number;
  auto_respond_enabled: boolean;
  created_at: string;
}

export interface Template {
  id: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  updated_at: string | null;
}

export interface Lead {
  id: number;
  name: string;
  phone: string;
  source_email: string;
  lead_source_id: number;
  gmail_uid: string;
  created_at: string;
  updated_at: string | null;
  response_sent: boolean;
  response_status: string | null;
}

export interface WatcherStatus {
  status: 'running' | 'stopped' | 'failed';
  last_sync: string | null;
  heartbeat: string | null;
  error: string | null;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  database: {
    connected: boolean;
    message: string;
  };
  watchers: {
    active_count: number;
    heartbeats: Record<string, string>;
  };
  errors: {
    count_24h: number;
    recent_errors: Array<{
      timestamp: string;
      action: string;
      details: string;
    }>;
  };
}

export interface Settings {
  sync_interval_seconds: number;
  regex_timeout_ms: number;
  session_timeout_hours: number;
  max_leads_per_page: number;
  enable_auto_restart: boolean;
}
```

---

## Styling Guidelines

### Tailwind CSS Conventions

**Colors**:
- Primary: `blue-600` (buttons, links)
- Success: `green-600` (success messages, running status)
- Warning: `yellow-600` (warnings, degraded status)
- Danger: `red-600` (errors, delete buttons, stopped status)
- Neutral: `gray-600` (text, borders)

**Spacing**:
- Container padding: `p-6`
- Section spacing: `space-y-6`
- Form field spacing: `space-y-4`

**Typography**:
- Page title: `text-3xl font-bold`
- Section title: `text-xl font-semibold`
- Body text: `text-base`
- Small text: `text-sm text-gray-600`

**Components**:
- Button: `px-4 py-2 rounded-md font-medium`
- Input: `px-3 py-2 border rounded-md`
- Card: `bg-white shadow rounded-lg p-6`

---

## Testing Strategy

### Unit Tests

**What to Test**:
- Component rendering
- User interactions (clicks, form submissions)
- State management
- Utility functions
- Form validation

**Example**:
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentForm } from './AgentForm';

describe('AgentForm', () => {
  it('validates email format', async () => {
    render(<AgentForm />);
    
    const emailInput = screen.getByLabelText('Email');
    fireEvent.change(emailInput, { target: { value: 'invalid' } });
    fireEvent.blur(emailInput);
    
    expect(await screen.findByText('Invalid email format')).toBeInTheDocument();
  });
});
```

### Integration Tests

**What to Test**:
- Authentication flow
- API integration
- Navigation
- Error handling

**Example**:
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { App } from './App';

const server = setupServer(
  rest.get('/api/v1/agents', (req, res, ctx) => {
    return res(ctx.json({ agents: [] }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('App', () => {
  it('loads agents on mount', async () => {
    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument();
    });
  });
});
```

---

## Performance Considerations

### Optimization Strategies

1. **Code Splitting**: Use React.lazy() for route-based splitting
2. **Memoization**: Use React.memo() for expensive components
3. **Debouncing**: Debounce search inputs and API calls
4. **Pagination**: Limit data fetching with pagination
5. **Caching**: Cache API responses where appropriate

### Example:
```typescript
// Route-based code splitting
const AgentsPage = lazy(() => import('./pages/AgentsPage'));
const LeadsPage = lazy(() => import('./pages/LeadsPage'));

// Memoized component
const LeadTable = memo(({ leads }: { leads: Lead[] }) => {
  // Expensive rendering logic
});

// Debounced search
const debouncedSearch = useMemo(
  () => debounce((query: string) => {
    // API call
  }, 300),
  []
);
```

---

## Accessibility Guidelines

### WCAG 2.1 AA Compliance

1. **Keyboard Navigation**: All interactive elements accessible via keyboard
2. **ARIA Labels**: Proper labels for screen readers
3. **Color Contrast**: Minimum 4.5:1 contrast ratio
4. **Focus Indicators**: Visible focus states
5. **Error Messages**: Associated with form fields

### Example:
```typescript
<button
  aria-label="Delete agent"
  className="focus:ring-2 focus:ring-blue-500"
  onClick={handleDelete}
>
  <TrashIcon className="h-5 w-5" aria-hidden="true" />
</button>
```

---

## Error Handling Strategy

### Error Types

1. **Network Errors**: Connection failures
2. **API Errors**: 4xx/5xx responses
3. **Validation Errors**: Form validation failures
4. **Authentication Errors**: 401/403 responses

### Error Display

```typescript
interface ErrorDisplayProps {
  error: Error | null;
  onRetry?: () => void;
}

function ErrorDisplay({ error, onRetry }: ErrorDisplayProps) {
  if (!error) return null;

  return (
    <div className="bg-red-50 border border-red-200 rounded-md p-4">
      <p className="text-red-800">{error.message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-red-600 underline">
          Retry
        </button>
      )}
    </div>
  );
}
```

---

## Development Workflow

### Setup

```bash
# Install dependencies
cd frontend
npm install

# Start dev server
npm run dev

# Run tests
npm run test

# Build for production
npm run build

# Preview production build
npm run preview
```

### Git Workflow

1. Create feature branch: `git checkout -b feature/agent-management`
2. Implement feature with tests
3. Run tests: `npm run test`
4. Build: `npm run build`
5. Commit: `git commit -m "feat: add agent management"`
6. Push and create PR

---

## Implementation Checklist

### Phase 1: Foundation ✅
- [ ] Set up Vite + React + TypeScript project
- [ ] Configure Tailwind CSS
- [ ] Set up React Router
- [ ] Create AuthContext
- [ ] Create API service layer
- [ ] Create LoginPage
- [ ] Create DashboardLayout
- [ ] Create ProtectedRoute

### Phase 2: Dashboard ✅
- [ ] Create DashboardPage
- [ ] Create HealthMetrics component
- [ ] Create WatcherStatusGrid component
- [ ] Create RecentErrorsTable component
- [ ] Implement polling hook
- [ ] Add real-time updates

### Phase 3: Agent Management ✅
- [ ] Create AgentsPage
- [ ] Create AgentList component
- [ ] Create AgentForm component
- [ ] Create AgentDetail component
- [ ] Create ConfirmDialog component
- [ ] Add watcher controls
- [ ] Add form validation
- [ ] Write unit tests

### Phase 4: Lead Source Management ✅
- [ ] Create LeadSourcesPage
- [ ] Create LeadSourceList component
- [ ] Create LeadSourceForm component
- [ ] Create RegexTestHarness component
- [ ] Create VersionHistory component
- [ ] Add regex testing
- [ ] Add version rollback
- [ ] Write unit tests

### Phase 5: Template Management ✅
- [ ] Create TemplatesPage
- [ ] Create TemplateList component
- [ ] Create TemplateEditor component
- [ ] Create TemplatePreview component
- [ ] Add placeholder insertion
- [ ] Add version history
- [ ] Write unit tests

### Phase 6: Watcher Control ✅
- [ ] Create WatcherStatusDisplay component
- [ ] Create WatcherControls component
- [ ] Add real-time status updates
- [ ] Add confirmation dialogs
- [ ] Write unit tests

### Phase 7: Lead Viewing & Export ✅
- [ ] Create LeadsPage
- [ ] Create LeadTable component
- [ ] Create LeadFilters component
- [ ] Create LeadDetail component
- [ ] Add CSV export
- [ ] Add pagination
- [ ] Write unit tests

### Phase 8: Audit Logs & Settings ✅
- [ ] Create AuditLogsPage
- [ ] Create AuditLogTable component
- [ ] Create AuditLogFilters component
- [ ] Create SettingsPage
- [ ] Create SettingsForm component
- [ ] Write unit tests

### Phase 9: Toast Notifications ✅
- [ ] Create ToastContainer component
- [ ] Create Toast component
- [ ] Create ToastContext
- [ ] Create useToast hook
- [ ] Add error boundary
- [ ] Write unit tests

### Phase 10: Testing & Polish ✅
- [ ] Write integration tests
- [ ] Test authentication flow
- [ ] Test all CRUD operations
- [ ] Test error handling
- [ ] Test real-time updates
- [ ] Polish UI/UX
- [ ] Accessibility audit
- [ ] Performance optimization

---

## Timeline Estimate

### Optimistic (Full-time, experienced developer)
- **Phase 1**: 1-2 days
- **Phase 2**: 1 day
- **Phase 3**: 2 days
- **Phase 4**: 2-3 days
- **Phase 5**: 2-3 days
- **Phase 6**: 1 day
- **Phase 7**: 2 days
- **Phase 8**: 1-2 days
- **Phase 9**: 1 day
- **Phase 10**: 2-3 days

**Total**: 15-21 days (3-4 weeks)

### Realistic (Part-time or learning curve)
- **Total**: 4-6 weeks

---

## Success Criteria

### Functional Requirements
- ✅ All CRUD operations working
- ✅ Real-time updates functioning
- ✅ Form validation working
- ✅ Error handling implemented
- ✅ Authentication flow complete

### Non-Functional Requirements
- ✅ 70%+ test coverage
- ✅ Responsive design (mobile-friendly)
- ✅ Accessible (WCAG 2.1 AA)
- ✅ Fast load times (< 3s)
- ✅ Type-safe (no TypeScript errors)

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Set up development environment**
3. **Begin Phase 1** (Foundation)
4. **Iterate and refine** based on feedback

---

## Appendix

### Useful Resources

- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [React Router Docs](https://reactrouter.com/)
- [React Hook Form Docs](https://react-hook-form.com/)
- [Zod Documentation](https://zod.dev/)
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)

### Design Inspiration

- [Tailwind UI Components](https://tailwindui.com/)
- [Headless UI Components](https://headlessui.com/)
- [Heroicons](https://heroicons.com/)

---

**Document Version**: 1.0  
**Last Updated**: March 3, 2026  
**Status**: Ready for Implementation
