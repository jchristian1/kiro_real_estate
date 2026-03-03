/**
 * Unit tests for LeadSourcesPage component
 *
 * Requirements: 23.1, 23.2, 23.4, 23.5
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { LeadSourcesPage } from './LeadSourcesPage';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

// Stub out RegexVersionHistory to keep tests focused on the page
vi.mock('../components/RegexVersionHistory', () => ({
  RegexVersionHistory: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="regex-version-history">
      <button onClick={onClose}>Close History</button>
    </div>
  ),
}));

const mockLeadSources = [
  {
    id: 1,
    name: 'Zillow Leads',
    regex_pattern: '(?i)zillow',
    description: 'Zillow lead emails',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Realtor Leads',
    regex_pattern: '(?i)realtor',
    description: null,
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
];

describe('LeadSourcesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<LeadSourcesPage />);
    expect(screen.getByText('Loading lead sources...')).toBeInTheDocument();
  });

  it('renders lead sources after loading', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
    render(<LeadSourcesPage />);

    await waitFor(() => {
      expect(screen.getByText('Zillow Leads')).toBeInTheDocument();
      expect(screen.getByText('Realtor Leads')).toBeInTheDocument();
    });
  });

  it('shows empty state when no lead sources', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: [] } });
    render(<LeadSourcesPage />);

    await waitFor(() => {
      expect(screen.getByText('No lead sources configured')).toBeInTheDocument();
    });
  });

  it('shows error state when fetch fails', async () => {
    mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    render(<LeadSourcesPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load lead sources')).toBeInTheDocument();
    });
  });

  describe('Delete confirmation', () => {
    it('shows confirmation dialog when delete is clicked', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
      render(<LeadSourcesPage />);

      await waitFor(() => screen.getByText('Zillow Leads'));

      const deleteButtons = screen.getAllByText('Delete');
      fireEvent.click(deleteButtons[0]);

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      expect(screen.getByTestId('confirm-dialog-title')).toHaveTextContent('Delete Lead Source');
      expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('Zillow Leads');
    });

    it('closes dialog on cancel', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
      render(<LeadSourcesPage />);

      await waitFor(() => screen.getByText('Zillow Leads'));

      fireEvent.click(screen.getAllByText('Delete')[0]);
      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();

      fireEvent.click(screen.getByTestId('confirm-dialog-cancel'));
      expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
    });

    it('calls delete API and removes item on confirm', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
      mockedAxios.delete = vi.fn().mockResolvedValue({});
      render(<LeadSourcesPage />);

      await waitFor(() => screen.getByText('Zillow Leads'));

      fireEvent.click(screen.getAllByText('Delete')[0]);
      fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));

      await waitFor(() => {
        expect(mockedAxios.delete).toHaveBeenCalledWith(
          expect.stringContaining('/lead-sources/1')
        );
        expect(screen.queryByText('Zillow Leads')).not.toBeInTheDocument();
      });
    });
  });

  describe('Version history', () => {
    it('opens version history panel when History is clicked', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
      render(<LeadSourcesPage />);

      await waitFor(() => screen.getByText('Zillow Leads'));

      const historyButtons = screen.getAllByText('History');
      fireEvent.click(historyButtons[0]);

      expect(screen.getByTestId('regex-version-history')).toBeInTheDocument();
    });

    it('closes version history panel when close is triggered', async () => {
      mockedAxios.get = vi.fn().mockResolvedValue({ data: { lead_sources: mockLeadSources } });
      render(<LeadSourcesPage />);

      await waitFor(() => screen.getByText('Zillow Leads'));

      fireEvent.click(screen.getAllByText('History')[0]);
      expect(screen.getByTestId('regex-version-history')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Close History'));
      expect(screen.queryByTestId('regex-version-history')).not.toBeInTheDocument();
    });
  });
});
