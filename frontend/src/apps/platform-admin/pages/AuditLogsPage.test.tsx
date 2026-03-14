/**
 * Tests for AuditLogsPage
 * Requirements: 23.4, 23.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { AuditLogsPage } from './AuditLogsPage';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

const mockLogs = [
  { id: 1, timestamp: '2024-01-15T10:00:00Z', user_id: 1, username: 'admin', action: 'agent_created', resource_type: 'agent', resource_id: 1, details: 'Created agent1' },
  { id: 2, timestamp: '2024-01-15T11:00:00Z', user_id: 1, username: 'admin', action: 'template_deleted', resource_type: 'template', resource_id: 2, details: null },
];

const mockResponse = { data: { logs: mockLogs, total: 2, page: 1, per_page: 100, pages: 1 } };

describe('AuditLogsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading state', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<AuditLogsPage />);
    expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();
  });

  it('renders audit log table', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<AuditLogsPage />);
    await waitFor(() => expect(screen.getByTestId('audit-table')).toBeInTheDocument());
    expect(screen.getByText('agent_created')).toBeInTheDocument();
    expect(screen.getByText('template_deleted')).toBeInTheDocument();
  });

  it('shows empty state', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { logs: [], total: 0, page: 1, per_page: 100, pages: 0 } });
    render(<AuditLogsPage />);
    await waitFor(() => expect(screen.getByTestId('audit-empty')).toBeInTheDocument());
  });

  it('shows error state', async () => {
    mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    render(<AuditLogsPage />);
    await waitFor(() => expect(screen.getByText('Failed to load audit logs')).toBeInTheDocument());
  });

  it('renders filter controls', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<AuditLogsPage />);
    await waitFor(() => screen.getByTestId('audit-filters'));
    expect(screen.getByTestId('filter-action')).toBeInTheDocument();
    expect(screen.getByTestId('filter-user-id')).toBeInTheDocument();
    expect(screen.getByTestId('filter-start-date')).toBeInTheDocument();
    expect(screen.getByTestId('filter-end-date')).toBeInTheDocument();
  });
});
