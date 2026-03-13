/**
 * Unit tests for AgentsPage component
 *
 * **Validates: Requirements 23.4, 23.5**
 *
 * Tests cover:
 * - Loading state display
 * - Error state display
 * - Renders list of agents with agent_id, email, status
 * - Empty state when no agents
 * - Delete button triggers ConfirmDialog showing agent name
 * - Confirming delete calls DELETE /api/v1/agents/{agent_id}
 * - Cancelling delete does not call API
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { AgentsPage } from './AgentsPage';

vi.mock('axios');
const mockedAxios = axios as unknown as {
  get: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const mockAgents = [
  {
    id: 1,
    agent_id: 'agent-alpha',
    email: 'alpha@example.com',
    created_at: '2024-01-10T08:00:00Z',
    updated_at: '2024-01-10T09:00:00Z',
    watcher_status: 'running',
  },
  {
    id: 2,
    agent_id: 'agent-beta',
    email: 'beta@example.com',
    created_at: '2024-01-11T08:00:00Z',
    updated_at: '2024-01-11T09:00:00Z',
    watcher_status: 'stopped',
  },
];

describe('AgentsPage', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading state', () => {
    it('shows loading indicator while fetching agents', () => {
      mockedAxios.get = vi.fn(() => new Promise(() => {})); // never resolves

      render(<AgentsPage />);

      expect(screen.getByText('Loading agents...')).toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('shows error message when fetch fails', async () => {
      mockedAxios.get = vi.fn(() => Promise.reject(new Error('Network error')));

      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load agents')).toBeInTheDocument();
      });
    });
  });

  describe('Agent list rendering', () => {
    beforeEach(() => {
      mockedAxios.get = vi.fn(() =>
        Promise.resolve({ data: { agents: mockAgents } })
      );
    });

    it('renders agent_id for each agent', async () => {
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('agent-alpha')).toBeInTheDocument();
        expect(screen.getByText('agent-beta')).toBeInTheDocument();
      });
    });

    it('renders email for each agent', async () => {
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('alpha@example.com')).toBeInTheDocument();
        expect(screen.getByText('beta@example.com')).toBeInTheDocument();
      });
    });

    it('renders watcher status for each agent', async () => {
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('running')).toBeInTheDocument();
        expect(screen.getByText('stopped')).toBeInTheDocument();
      });
    });

    it('renders a Delete button for each agent', async () => {
      render(<AgentsPage />);

      await waitFor(() => {
        const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
        expect(deleteButtons).toHaveLength(2);
      });
    });

    it('renders "Not Started" for agents with null watcher_status', async () => {
      mockedAxios.get = vi.fn(() =>
        Promise.resolve({
          data: {
            agents: [
              { ...mockAgents[0], watcher_status: null },
            ],
          },
        })
      );

      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('Not Started')).toBeInTheDocument();
      });
    });
  });

  describe('Empty state', () => {
    it('shows empty state message when no agents exist', async () => {
      mockedAxios.get = vi.fn(() =>
        Promise.resolve({ data: { agents: [] } })
      );

      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText('No agents configured')).toBeInTheDocument();
      });
    });

    it('does not render the agents table when list is empty', async () => {
      mockedAxios.get = vi.fn(() =>
        Promise.resolve({ data: { agents: [] } })
      );

      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.queryByRole('table')).not.toBeInTheDocument();
      });
    });
  });

  describe('Delete confirmation dialog', () => {
    beforeEach(() => {
      mockedAxios.get = vi.fn(() =>
        Promise.resolve({ data: { agents: mockAgents } })
      );
      mockedAxios.delete = vi.fn(() => Promise.resolve({ data: {} }));
    });

    it('opens ConfirmDialog with agent name when Delete is clicked', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));
      const [firstDeleteBtn] = screen.getAllByRole('button', { name: /delete/i });
      await user.click(firstDeleteBtn);

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      expect(screen.getByTestId('confirm-dialog-message')).toHaveTextContent('agent-alpha');
    });

    it('dialog is not visible before Delete is clicked', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));

      expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
    });

    it('calls DELETE /api/v1/agents/{agent_id} when confirmed', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));
      const [firstDeleteBtn] = screen.getAllByRole('button', { name: /delete/i });
      await user.click(firstDeleteBtn);

      await user.click(screen.getByTestId('confirm-dialog-confirm'));

      await waitFor(() => {
        expect(mockedAxios.delete).toHaveBeenCalledWith(
          expect.stringContaining('/agents/agent-alpha')
        );
      });
    });

    it('removes deleted agent from the list after confirmation', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));
      const [firstDeleteBtn] = screen.getAllByRole('button', { name: /delete/i });
      await user.click(firstDeleteBtn);

      await user.click(screen.getByTestId('confirm-dialog-confirm'));

      await waitFor(() => {
        expect(screen.queryByText('agent-alpha')).not.toBeInTheDocument();
        expect(screen.getByText('agent-beta')).toBeInTheDocument();
      });
    });

    it('does not call DELETE when cancel is clicked', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));
      const [firstDeleteBtn] = screen.getAllByRole('button', { name: /delete/i });
      await user.click(firstDeleteBtn);

      await user.click(screen.getByTestId('confirm-dialog-cancel'));

      expect(mockedAxios.delete).not.toHaveBeenCalled();
    });

    it('closes dialog after cancelling without removing agent', async () => {
      render(<AgentsPage />);

      await waitFor(() => screen.getAllByRole('button', { name: /delete/i }));
      const [firstDeleteBtn] = screen.getAllByRole('button', { name: /delete/i });
      await user.click(firstDeleteBtn);

      await user.click(screen.getByTestId('confirm-dialog-cancel'));

      await waitFor(() => {
        expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
      });
      expect(screen.getByText('agent-alpha')).toBeInTheDocument();
    });
  });
});
