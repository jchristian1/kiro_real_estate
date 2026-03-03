/**
 * Tests for TemplateVersionHistory component
 * Requirements: 23.4
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { TemplateVersionHistory } from './TemplateVersionHistory';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

const mockVersions = [
  { version: 2, name: 'T', subject: 'Subj v2', body: 'Body v2', created_at: '2024-02-01T00:00:00Z', created_by: 1 },
  { version: 1, name: 'T', subject: 'Subj v1', body: 'Body v1', created_at: '2024-01-01T00:00:00Z', created_by: 1 },
];

const props = { templateId: 1, templateName: 'Welcome', onClose: vi.fn(), onRollbackSuccess: vi.fn() };

describe('TemplateVersionHistory', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading state', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<TemplateVersionHistory {...props} />);
    expect(screen.getByTestId('version-history-loading')).toBeInTheDocument();
  });

  it('renders versions', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<TemplateVersionHistory {...props} />);
    await waitFor(() => expect(screen.getByTestId('version-list')).toBeInTheDocument());
    expect(screen.getByTestId('version-item-2')).toBeInTheDocument();
    expect(screen.getByTestId('version-item-1')).toBeInTheDocument();
  });

  it('marks latest as current', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<TemplateVersionHistory {...props} />);
    await waitFor(() => screen.getByTestId('version-list'));
    expect(screen.getByText('Current')).toBeInTheDocument();
    expect(screen.queryByTestId('rollback-button-2')).not.toBeInTheDocument();
    expect(screen.getByTestId('rollback-button-1')).toBeInTheDocument();
  });

  it('shows confirm dialog on rollback click', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<TemplateVersionHistory {...props} />);
    await waitFor(() => screen.getByTestId('version-list'));
    fireEvent.click(screen.getByTestId('rollback-button-1'));
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('version 1');
  });

  it('calls rollback API and onRollbackSuccess', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    mockedAxios.post = vi.fn().mockResolvedValue({});
    render(<TemplateVersionHistory {...props} />);
    await waitFor(() => screen.getByTestId('version-list'));
    fireEvent.click(screen.getByTestId('rollback-button-1'));
    fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/templates/1/rollback'), { version: 1 });
      expect(props.onRollbackSuccess).toHaveBeenCalled();
    });
  });

  it('calls onClose when close button clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { versions: mockVersions } });
    render(<TemplateVersionHistory {...props} />);
    await waitFor(() => screen.getByTestId('version-list'));
    fireEvent.click(screen.getByTestId('version-history-close'));
    expect(props.onClose).toHaveBeenCalled();
  });
});
