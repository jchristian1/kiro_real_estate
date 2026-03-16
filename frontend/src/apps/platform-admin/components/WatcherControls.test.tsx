/**
 * Tests for WatcherControls component
 * Requirements: 23.4
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import { WatcherControls } from './WatcherControls';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

const mockWatchers = [
  { agent_id: 'agent1', status: 'running', last_heartbeat: null, last_sync: null, error: null },
  { agent_id: 'agent2', status: 'stopped', last_heartbeat: null, last_sync: null, error: null },
];

describe('WatcherControls', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading state', () => {
    mockedAxios.get = vi.fn(() => new Promise(() => {}));
    render(<WatcherControls />);
    expect(screen.getByTestId('watcher-controls-loading')).toBeInTheDocument();
  });

  it('renders watcher cards', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    render(<WatcherControls />);
    await waitFor(() => {
      expect(screen.getByTestId('watcher-card-agent1')).toBeInTheDocument();
      expect(screen.getByTestId('watcher-card-agent2')).toBeInTheDocument();
    });
  });

  it('shows stop button for running watcher', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('watcher-card-agent1'));
    expect(screen.getByTestId('stop-btn-agent1')).toBeInTheDocument();
    expect(screen.queryByTestId('start-btn-agent1')).not.toBeInTheDocument();
  });

  it('shows start button for stopped watcher', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('watcher-card-agent2'));
    expect(screen.getByTestId('start-btn-agent2')).toBeInTheDocument();
    expect(screen.queryByTestId('stop-btn-agent2')).not.toBeInTheDocument();
  });

  it('shows confirmation dialog when stop is clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('stop-btn-agent1'));
    fireEvent.click(screen.getByTestId('stop-btn-agent1'));
    expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('agent1');
  });

  it('cancels stop when cancel clicked', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('stop-btn-agent1'));
    fireEvent.click(screen.getByTestId('stop-btn-agent1'));
    fireEvent.click(screen.getByTestId('confirm-dialog-cancel'));
    expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  });

  it('calls stop API on confirm', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    mockedAxios.post = vi.fn().mockResolvedValue({});
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('stop-btn-agent1'));
    fireEvent.click(screen.getByTestId('stop-btn-agent1'));
    fireEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/watchers/agent1/stop'));
    });
  });

  it('calls start API directly without confirmation', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    mockedAxios.post = vi.fn().mockResolvedValue({});
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('start-btn-agent2'));
    fireEvent.click(screen.getByTestId('start-btn-agent2'));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/watchers/agent2/start'));
    });
  });

  it('calls sync API', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: mockWatchers } });
    mockedAxios.post = vi.fn().mockResolvedValue({});
    render(<WatcherControls />);
    await waitFor(() => screen.getByTestId('sync-btn-agent1'));
    fireEvent.click(screen.getByTestId('sync-btn-agent1'));
    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/watchers/agent1/sync'));
    });
  });

  it('shows empty state when no watchers', async () => {
    mockedAxios.get = vi.fn().mockResolvedValue({ data: { watchers: [] } });
    render(<WatcherControls />);
    await waitFor(() => expect(screen.getByTestId('watcher-controls-empty')).toBeInTheDocument());
  });
});
