/**
 * Tests for LeadsPage component
 * Requirements: 23.4
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { LeadsPage } from './LeadsPage';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

// Mock ToastContext
vi.mock('../contexts/ToastContext', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const mockLeads = [
  { id: 1, name: 'John Doe', phone: '555-1234', source_email: 'leads@example.com', gmail_uid: 'uid1', created_at: '2024-01-15T10:00:00Z', response_sent: true, response_status: 'success' },
  { id: 2, name: 'Jane Smith', phone: '555-5678', source_email: 'leads@example.com', gmail_uid: 'uid2', created_at: '2024-01-16T10:00:00Z', response_sent: false, response_status: null },
];

const mockResponse = { data: { leads: mockLeads, total: 2, page: 1, per_page: 50, pages: 1 } };

describe('LeadsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading state', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<LeadsPage />);
    expect(screen.getByText('Loading leads...')).toBeInTheDocument();
  });

  it('renders leads table', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => expect(screen.getByTestId('leads-table')).toBeInTheDocument());
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
  });

  it('shows empty state when no leads', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { leads: [], total: 0, page: 1, per_page: 50, pages: 0 } });
    render(<LeadsPage />);
    await waitFor(() => expect(screen.getByTestId('leads-empty')).toBeInTheDocument());
  });

  it('shows lead detail on view click', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => screen.getByTestId('leads-table'));
    fireEvent.click(screen.getByTestId('view-lead-1'));
    expect(screen.getByTestId('lead-detail')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('goes back from detail view', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => screen.getByTestId('leads-table'));
    fireEvent.click(screen.getByTestId('view-lead-1'));
    fireEvent.click(screen.getByText('← Back'));
    expect(screen.getByTestId('leads-table')).toBeInTheDocument();
  });

  it('renders filter controls', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => screen.getByTestId('lead-filters'));
    expect(screen.getByTestId('filter-agent-id')).toBeInTheDocument();
    expect(screen.getByTestId('filter-start-date')).toBeInTheDocument();
    expect(screen.getByTestId('filter-end-date')).toBeInTheDocument();
    expect(screen.getByTestId('filter-response')).toBeInTheDocument();
  });

  it('renders export button', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => screen.getByTestId('export-btn'));
    expect(screen.getByTestId('export-btn')).toBeInTheDocument();
  });

  it('shows response sent badge', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);
    render(<LeadsPage />);
    await waitFor(() => screen.getByTestId('leads-table'));
    expect(screen.getAllByText('Sent').length).toBeGreaterThan(0);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('shows error state on fetch failure', async () => {
    mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    render(<LeadsPage />);
    await waitFor(() => expect(screen.getByText('Failed to load leads')).toBeInTheDocument());
  });
});
