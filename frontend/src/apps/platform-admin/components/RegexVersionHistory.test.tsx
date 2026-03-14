/**
 * Tests for RegexVersionHistory component
 *
 * Requirements: 9.5, 9.6
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { RegexVersionHistory } from './RegexVersionHistory';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

const mockVersions = [
  {
    version: 3,
    name_regex: 'Name:\\s*(.+)',
    phone_regex: 'Phone:\\s*([\\d-]+)',
    identifier_snippet: 'New Lead v3',
    created_at: '2024-03-01T12:00:00Z',
    created_by: 1,
  },
  {
    version: 2,
    name_regex: 'Name:\\s*(\\w+)',
    phone_regex: 'Tel:\\s*([\\d-]+)',
    identifier_snippet: 'New Lead v2',
    created_at: '2024-02-01T12:00:00Z',
    created_by: 1,
  },
  {
    version: 1,
    name_regex: 'Name: (.+)',
    phone_regex: 'Phone: ([\\d-]+)',
    identifier_snippet: 'New Lead v1',
    created_at: '2024-01-01T12:00:00Z',
    created_by: 1,
  },
];

const defaultProps = {
  leadSourceId: 42,
  leadSourceName: 'Zillow Leads',
  onClose: vi.fn(),
  onRollbackSuccess: vi.fn(),
};

describe('RegexVersionHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<RegexVersionHistory {...defaultProps} />);
    expect(screen.getByTestId('version-history-loading')).toBeInTheDocument();
  });

  it('renders version list after loading', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('version-list')).toBeInTheDocument();
    });

    expect(screen.getByTestId('version-item-3')).toBeInTheDocument();
    expect(screen.getByTestId('version-item-2')).toBeInTheDocument();
    expect(screen.getByTestId('version-item-1')).toBeInTheDocument();
  });

  it('marks the first version as current', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    const currentBadge = screen.getByText('Current');
    expect(currentBadge).toBeInTheDocument();
    // Current badge should be inside version-item-3 (latest)
    expect(screen.getByTestId('version-item-3')).toContainElement(currentBadge);
  });

  it('does not show rollback button for the current (latest) version', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    expect(screen.queryByTestId('rollback-button-3')).not.toBeInTheDocument();
    expect(screen.getByTestId('rollback-button-2')).toBeInTheDocument();
    expect(screen.getByTestId('rollback-button-1')).toBeInTheDocument();
  });

  it('shows version details when Details button is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('toggle-version-2'));
    expect(screen.getByTestId('version-details-2')).toBeInTheDocument();
    expect(screen.getByText('Name:\\s*(\\w+)')).toBeInTheDocument();
  });

  it('hides version details when Hide button is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('toggle-version-2'));
    expect(screen.getByTestId('version-details-2')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('toggle-version-2'));
    expect(screen.queryByTestId('version-details-2')).not.toBeInTheDocument();
  });

  it('shows confirmation dialog when rollback is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('rollback-button-2'));

    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-dialog-title')).toHaveTextContent('Rollback Regex Profile');
    expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('version 2');
    expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('Zillow Leads');
  });

  it('cancels rollback when cancel is clicked in dialog', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('rollback-button-1'));
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('confirm-dialog-cancel'));
    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  });

  it('calls rollback API and onRollbackSuccess on confirm', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    mockedAxios.post = vi.fn().mockResolvedValue({});
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('rollback-button-1'));
    fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/lead-sources/42/rollback'),
        { version: 1 }
      );
      expect(defaultProps.onRollbackSuccess).toHaveBeenCalled();
    });
  });

  it('shows error message when rollback API fails', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    mockedAxios.post = vi.fn().mockRejectedValue({
      response: { data: { message: 'Rollback failed' } },
    });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('rollback-button-1'));
    fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));

    await waitFor(() => {
      expect(screen.getByTestId('rollback-error')).toHaveTextContent('Rollback failed');
    });
  });

  it('shows error state when API fetch fails', async () => {
    mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('version-history-error')).toBeInTheDocument();
    });
  });

  it('shows empty state when no versions exist', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: [] } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('version-history-empty')).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('version-history-close'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-list'));

    fireEvent.click(screen.getByTestId('version-history-backdrop'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('displays lead source name in the header', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<RegexVersionHistory {...defaultProps} />);

    await waitFor(() => screen.getByTestId('version-history-title'));
    expect(screen.getByText('Zillow Leads')).toBeInTheDocument();
  });
});
