/**
 * Unit tests for AgentDetail component
 *
 * **Validates: Requirements 1.6, 23.4**
 *
 * Tests cover:
 * - Loading state display
 * - Error state display
 * - Agent configuration rendering (agent_id, email, timestamps)
 * - Watcher status display (badge colors, heartbeat, last sync)
 * - Watcher control buttons (Start/Stop/Sync visibility and behavior)
 * - Action success and error feedback
 * - Back button callback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { AgentDetail, AgentDetailData, WatcherStatus } from './AgentDetail';

vi.mock('axios');
const mockedAxios = axios as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  defaults: { withCredentials: boolean };
};

const mockAgent: AgentDetailData = {
  id: 1,
  agent_id: 'agent1',
  email: 'agent1@example.com',
  created_at: '2024-01-15T10:00:00Z',
  updated_at: '2024-01-15T11:00:00Z',
};

const mockWatcherRunning: WatcherStatus = {
  agent_id: 'agent1',
  status: 'running',
  last_heartbeat: '2024-01-15T10:05:00Z',
  last_sync: '2024-01-15T10:04:00Z',
  error: null,
};

const mockWatcherStopped: WatcherStatus = {
  agent_id: 'agent1',
  status: 'stopped',
  last_heartbeat: null,
  last_sync: '2024-01-15T09:00:00Z',
  error: null,
};

const mockWatcherFailed: WatcherStatus = {
  agent_id: 'agent1',
  status: 'failed',
  last_heartbeat: '2024-01-15T09:30:00Z',
  last_sync: '2024-01-15T09:29:00Z',
  error: 'Connection timeout',
};

const setupMocks = (watcher: WatcherStatus | null = mockWatcherRunning) => {
  mockedAxios.get = vi.fn((url: string) => {
    if (url.includes('/agents/')) {
      return Promise.resolve({ data: mockAgent });
    }
    if (url.includes('/watchers/status')) {
      return Promise.resolve({
        data: { watchers: watcher ? [watcher] : [] },
      });
    }
    return Promise.reject(new Error('Unknown endpoint'));
  });
  mockedAxios.post = vi.fn(() => Promise.resolve({ data: {} }));
};

describe('AgentDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading state', () => {
    it('shows loading indicator while fetching', () => {
      mockedAxios.get = vi.fn(() => new Promise(() => {})); // never resolves

      render(<AgentDetail agentId="agent1" />);

      expect(screen.getByTestId('agent-detail-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading agent details...')).toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('shows error message when fetch fails', async () => {
      mockedAxios.get = vi.fn(() => Promise.reject(new Error('Network error')));

      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('agent-detail-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to load agent details')).toBeInTheDocument();
    });
  });

  describe('Agent configuration display', () => {
    it('renders agent_id', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('agent-id')).toHaveTextContent('agent1');
      });
    });

    it('renders email', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('agent-email')).toHaveTextContent('agent1@example.com');
      });
    });

    it('renders created_at timestamp', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('agent-created-at')).toBeInTheDocument();
      });
    });

    it('renders updated_at timestamp', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('agent-updated-at')).toBeInTheDocument();
      });
    });

    it('renders agent_id in page heading', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByText('Agent: agent1')).toBeInTheDocument();
      });
    });
  });

  describe('Watcher status display', () => {
    it('shows running status badge with green color', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        const badge = screen.getByTestId('watcher-status-badge');
        expect(badge).toHaveTextContent('running');
        expect(badge).toHaveClass('bg-green-100', 'text-green-800');
      });
    });

    it('shows stopped status badge with gray color', async () => {
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        const badge = screen.getByTestId('watcher-status-badge');
        expect(badge).toHaveTextContent('stopped');
        expect(badge).toHaveClass('bg-gray-100', 'text-gray-800');
      });
    });

    it('shows failed status badge with red color', async () => {
      setupMocks(mockWatcherFailed);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        const badge = screen.getByTestId('watcher-status-badge');
        expect(badge).toHaveTextContent('failed');
        expect(badge).toHaveClass('bg-red-100', 'text-red-800');
      });
    });

    it('shows last heartbeat', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('watcher-last-heartbeat')).toBeInTheDocument();
      });
    });

    it('shows last sync', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('watcher-last-sync')).toBeInTheDocument();
      });
    });

    it('shows "Never" for null heartbeat', async () => {
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('watcher-last-heartbeat')).toHaveTextContent('Never');
      });
    });

    it('shows error message when watcher has error', async () => {
      setupMocks(mockWatcherFailed);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('watcher-error')).toHaveTextContent('Connection timeout');
      });
    });

    it('does not show error section when no error', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.queryByTestId('watcher-error')).not.toBeInTheDocument();
      });
    });

    it('shows "not started" message when no watcher status found', async () => {
      setupMocks(null);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('watcher-not-started')).toBeInTheDocument();
      });
    });
  });

  describe('Watcher control buttons', () => {
    it('shows Start button when watcher is stopped', async () => {
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('start-button')).toBeInTheDocument();
      });
    });

    it('does not show Stop button when watcher is stopped', async () => {
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.queryByTestId('stop-button')).not.toBeInTheDocument();
      });
    });

    it('shows Stop button when watcher is running', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('stop-button')).toBeInTheDocument();
      });
    });

    it('does not show Start button when watcher is running', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.queryByTestId('start-button')).not.toBeInTheDocument();
      });
    });

    it('always shows Sync button', async () => {
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('sync-button')).toBeInTheDocument();
      });
    });

    it('shows Sync button when watcher is stopped', async () => {
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('sync-button')).toBeInTheDocument();
      });
    });

    it('shows Start button when no watcher status exists', async () => {
      setupMocks(null);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.getByTestId('start-button')).toBeInTheDocument();
      });
    });
  });

  describe('Watcher control actions', () => {
    it('calls start endpoint when Start is clicked', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('start-button'));
      await user.click(screen.getByTestId('start-button'));

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/watchers/agent1/start')
      );
    });

    it('calls stop endpoint when Stop is clicked', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('stop-button'));
      await user.click(screen.getByTestId('stop-button'));

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/watchers/agent1/stop')
      );
    });

    it('calls sync endpoint when Sync is clicked', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('sync-button'));
      await user.click(screen.getByTestId('sync-button'));

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/watchers/agent1/sync')
      );
    });

    it('shows success message after successful start', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherStopped);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('start-button'));
      await user.click(screen.getByTestId('start-button'));

      await waitFor(() => {
        expect(screen.getByTestId('action-success')).toHaveTextContent(
          'Watcher started successfully'
        );
      });
    });

    it('shows success message after successful stop', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('stop-button'));
      await user.click(screen.getByTestId('stop-button'));

      await waitFor(() => {
        expect(screen.getByTestId('action-success')).toHaveTextContent(
          'Watcher stopped successfully'
        );
      });
    });

    it('shows success message after successful sync', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherRunning);
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('sync-button'));
      await user.click(screen.getByTestId('sync-button'));

      await waitFor(() => {
        expect(screen.getByTestId('action-success')).toHaveTextContent(
          'Sync triggered successfully'
        );
      });
    });

    it('shows error message when action fails', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherStopped);
      mockedAxios.post = vi.fn(() =>
        Promise.reject({ response: { data: { detail: 'Watcher already running' } } })
      );
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('start-button'));
      await user.click(screen.getByTestId('start-button'));

      await waitFor(() => {
        expect(screen.getByTestId('action-error')).toHaveTextContent('Watcher already running');
      });
    });

    it('disables all buttons while an action is in progress', async () => {
      const user = userEvent.setup();
      setupMocks(mockWatcherStopped);
      // Make post never resolve so we can check disabled state
      mockedAxios.post = vi.fn(() => new Promise(() => {}));
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => screen.getByTestId('start-button'));
      await user.click(screen.getByTestId('start-button'));

      expect(screen.getByTestId('start-button')).toBeDisabled();
      expect(screen.getByTestId('sync-button')).toBeDisabled();
    });
  });

  describe('Back button', () => {
    it('renders back button when onBack is provided', async () => {
      setupMocks();
      const onBack = vi.fn();
      render(<AgentDetail agentId="agent1" onBack={onBack} />);

      await waitFor(() => {
        expect(screen.getByTestId('back-button')).toBeInTheDocument();
      });
    });

    it('does not render back button when onBack is not provided', async () => {
      setupMocks();
      render(<AgentDetail agentId="agent1" />);

      await waitFor(() => {
        expect(screen.queryByTestId('back-button')).not.toBeInTheDocument();
      });
    });

    it('calls onBack when back button is clicked', async () => {
      const user = userEvent.setup();
      setupMocks();
      const onBack = vi.fn();
      render(<AgentDetail agentId="agent1" onBack={onBack} />);

      await waitFor(() => screen.getByTestId('back-button'));
      await user.click(screen.getByTestId('back-button'));

      expect(onBack).toHaveBeenCalledOnce();
    });
  });
});
