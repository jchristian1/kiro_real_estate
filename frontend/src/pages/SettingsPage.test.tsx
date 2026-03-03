/**
 * Tests for SettingsPage
 * Requirements: 23.4, 23.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import axios from 'axios';
import { SettingsPage } from './SettingsPage';
import { ToastProvider } from '../contexts/ToastContext';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

const mockSettings = {
  sync_interval_seconds: 300,
  regex_timeout_ms: 1000,
  session_timeout_hours: 24,
  max_leads_per_page: 100,
  enable_auto_restart: true,
};

const renderPage = () =>
  render(
    <ToastProvider>
      <SettingsPage />
    </ToastProvider>
  );

describe('SettingsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading state', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading settings...')).toBeInTheDocument();
  });

  it('renders settings form with values', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('settings-form')).toBeInTheDocument());
    expect((screen.getByTestId('input-sync_interval_seconds') as HTMLInputElement).value).toBe('300');
    expect((screen.getByTestId('input-regex_timeout_ms') as HTMLInputElement).value).toBe('1000');
    expect((screen.getByTestId('input-session_timeout_hours') as HTMLInputElement).value).toBe('24');
    expect((screen.getByTestId('input-max_leads_per_page') as HTMLInputElement).value).toBe('100');
  });

  it('shows error state on fetch failure', async () => {
    mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Failed to load settings')).toBeInTheDocument());
  });

  it('validates number fields out of range', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => screen.getByTestId('input-sync_interval_seconds'));
    fireEvent.change(screen.getByTestId('input-sync_interval_seconds'), { target: { value: '10' } });
    await waitFor(() => expect(screen.getByTestId('error-sync_interval_seconds')).toBeInTheDocument());
    expect(screen.getByTestId('save-btn')).toBeDisabled();
  });

  it('save button disabled when no changes', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => screen.getByTestId('save-btn'));
    expect(screen.getByTestId('save-btn')).toBeDisabled();
  });

  it('enables save button when value changes', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => screen.getByTestId('input-sync_interval_seconds'));
    fireEvent.change(screen.getByTestId('input-sync_interval_seconds'), { target: { value: '600' } });
    await waitFor(() => expect(screen.getByTestId('save-btn')).not.toBeDisabled());
  });

  it('saves settings successfully', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    mockedAxios.put = vi.fn().mockResolvedValue({ data: { ...mockSettings, sync_interval_seconds: 600 } });
    renderPage();
    await waitFor(() => screen.getByTestId('input-sync_interval_seconds'));
    fireEvent.change(screen.getByTestId('input-sync_interval_seconds'), { target: { value: '600' } });
    await waitFor(() => expect(screen.getByTestId('save-btn')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('save-btn'));
    await waitFor(() => expect(mockedAxios.put).toHaveBeenCalled());
  });

  it('reset button restores original values', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => screen.getByTestId('input-sync_interval_seconds'));
    fireEvent.change(screen.getByTestId('input-sync_interval_seconds'), { target: { value: '600' } });
    await waitFor(() => expect(screen.getByTestId('reset-btn')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('reset-btn'));
    await waitFor(() => expect((screen.getByTestId('input-sync_interval_seconds') as HTMLInputElement).value).toBe('300'));
  });

  it('toggles boolean setting', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: mockSettings });
    renderPage();
    await waitFor(() => screen.getByTestId('toggle-enable_auto_restart'));
    const toggle = screen.getByTestId('toggle-enable_auto_restart');
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'false'));
  });
});
