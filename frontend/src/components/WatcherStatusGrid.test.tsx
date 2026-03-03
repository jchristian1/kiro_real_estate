/**
 * Unit tests for WatcherStatusGrid component
 * 
 * **Validates: Requirements 23.4**
 * 
 * Tests cover:
 * - Display of watcher status cards
 * - Status badge colors based on watcher state
 * - Timestamp formatting (relative and absolute)
 * - Error message display
 * - Empty state handling
 * - Refresh button functionality
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WatcherStatusGrid } from './WatcherStatusGrid';
import { WatcherStatus } from '../pages/DashboardPage';

describe('WatcherStatusGrid', () => {
  const mockWatchers: WatcherStatus[] = [
    {
      agent_id: 'agent1',
      status: 'running',
      last_heartbeat: '2024-01-15T10:00:00Z',
      last_sync: '2024-01-15T09:55:00Z',
      error: null,
    },
    {
      agent_id: 'agent2',
      status: 'stopped',
      last_heartbeat: null,
      last_sync: '2024-01-15T08:00:00Z',
      error: null,
    },
    {
      agent_id: 'agent3',
      status: 'failed',
      last_heartbeat: '2024-01-15T09:00:00Z',
      last_sync: '2024-01-15T08:55:00Z',
      error: 'Connection timeout',
    },
  ];

  const mockOnRefresh = vi.fn();

  describe('Component Structure', () => {
    it('should render component title', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('Watcher Status')).toBeInTheDocument();
    });

    it('should render refresh button', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('should call onRefresh when refresh button is clicked', async () => {
      const user = userEvent.setup();
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      expect(mockOnRefresh).toHaveBeenCalledTimes(1);
    });
  });

  describe('Watcher Cards Display', () => {
    it('should render all watcher cards', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('agent1')).toBeInTheDocument();
      expect(screen.getByText('agent2')).toBeInTheDocument();
      expect(screen.getByText('agent3')).toBeInTheDocument();
    });

    it('should display agent IDs', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      mockWatchers.forEach((watcher) => {
        expect(screen.getByText(watcher.agent_id)).toBeInTheDocument();
      });
    });

    it('should display last heartbeat label', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const labels = screen.getAllByText('Last Heartbeat');
      expect(labels.length).toBe(mockWatchers.length);
    });

    it('should display last sync label', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const labels = screen.getAllByText('Last Sync');
      expect(labels.length).toBe(mockWatchers.length);
    });
  });

  describe('Status Badge Display', () => {
    it('should display running status with green badge', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const runningBadge = screen.getByText('running');
      expect(runningBadge).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('should display stopped status with gray badge', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const stoppedBadge = screen.getByText('stopped');
      expect(stoppedBadge).toHaveClass('bg-gray-100', 'text-gray-800');
    });

    it('should display failed status with red badge', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const failedBadge = screen.getByText('failed');
      expect(failedBadge).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('should display unknown status with yellow badge', () => {
      const unknownWatcher: WatcherStatus = {
        agent_id: 'agent4',
        status: 'unknown',
        last_heartbeat: null,
        last_sync: null,
        error: null,
      };

      render(<WatcherStatusGrid watchers={[unknownWatcher]} onRefresh={mockOnRefresh} />);

      const unknownBadge = screen.getByText('unknown');
      expect(unknownBadge).toHaveClass('bg-yellow-100', 'text-yellow-800');
    });
  });

  describe('Timestamp Formatting', () => {
    it('should display "Never" for null timestamps', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      // agent2 has null last_heartbeat
      const neverTexts = screen.getAllByText('Never');
      expect(neverTexts.length).toBeGreaterThan(0);
    });

    it('should format recent timestamps as relative time', () => {
      // Mock current time
      const now = new Date('2024-01-15T10:05:00Z');
      vi.setSystemTime(now);

      const recentWatcher: WatcherStatus = {
        agent_id: 'agent_recent',
        status: 'running',
        last_heartbeat: '2024-01-15T10:04:30Z', // 30 seconds ago
        last_sync: '2024-01-15T10:00:00Z', // 5 minutes ago
        error: null,
      };

      render(<WatcherStatusGrid watchers={[recentWatcher]} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('Just now')).toBeInTheDocument();
      expect(screen.getByText('5m ago')).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('should format timestamps in hours for older times', () => {
      const now = new Date('2024-01-15T12:00:00Z');
      vi.setSystemTime(now);

      const olderWatcher: WatcherStatus = {
        agent_id: 'agent_older',
        status: 'running',
        last_heartbeat: '2024-01-15T10:00:00Z', // 2 hours ago
        last_sync: '2024-01-15T09:00:00Z', // 3 hours ago
        error: null,
      };

      render(<WatcherStatusGrid watchers={[olderWatcher]} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('2h ago')).toBeInTheDocument();
      expect(screen.getByText('3h ago')).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('should format timestamps as full date for very old times', () => {
      const now = new Date('2024-01-16T10:00:00Z');
      vi.setSystemTime(now);

      const veryOldWatcher: WatcherStatus = {
        agent_id: 'agent_very_old',
        status: 'stopped',
        last_heartbeat: '2024-01-14T10:00:00Z', // 2 days ago
        last_sync: '2024-01-14T09:00:00Z',
        error: null,
      };

      render(<WatcherStatusGrid watchers={[veryOldWatcher]} onRefresh={mockOnRefresh} />);

      // Should display full locale string for dates > 24 hours
      const timestamp = new Date('2024-01-14T10:00:00Z').toLocaleString();
      expect(screen.getByText(timestamp)).toBeInTheDocument();

      vi.useRealTimers();
    });
  });

  describe('Error Display', () => {
    it('should display error message when present', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    });

    it('should display error label', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('should not display error section when error is null', () => {
      const noErrorWatcher: WatcherStatus = {
        agent_id: 'agent_no_error',
        status: 'running',
        last_heartbeat: '2024-01-15T10:00:00Z',
        last_sync: '2024-01-15T09:55:00Z',
        error: null,
      };

      render(<WatcherStatusGrid watchers={[noErrorWatcher]} onRefresh={mockOnRefresh} />);

      // Should not have error styling
      const card = screen.getByText('agent_no_error').closest('div');
      expect(card?.querySelector('.bg-red-50')).not.toBeInTheDocument();
    });

    it('should apply error styling to error message', () => {
      render(<WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />);

      const errorMessage = screen.getByText('Connection timeout');
      expect(errorMessage).toHaveClass('text-red-700');
    });
  });

  describe('Empty State', () => {
    it('should display empty state message when no watchers', () => {
      render(<WatcherStatusGrid watchers={[]} onRefresh={mockOnRefresh} />);

      expect(
        screen.getByText('No watchers configured. Create an agent to get started.')
      ).toBeInTheDocument();
    });

    it('should not display watcher cards when empty', () => {
      render(<WatcherStatusGrid watchers={[]} onRefresh={mockOnRefresh} />);

      expect(screen.queryByText('agent1')).not.toBeInTheDocument();
    });

    it('should still display refresh button when empty', () => {
      render(<WatcherStatusGrid watchers={[]} onRefresh={mockOnRefresh} />);

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long agent IDs with truncation', () => {
      const longIdWatcher: WatcherStatus = {
        agent_id: 'very_long_agent_id_that_should_be_truncated_in_display',
        status: 'running',
        last_heartbeat: '2024-01-15T10:00:00Z',
        last_sync: '2024-01-15T09:55:00Z',
        error: null,
      };

      render(<WatcherStatusGrid watchers={[longIdWatcher]} onRefresh={mockOnRefresh} />);

      const agentIdElement = screen.getByText(longIdWatcher.agent_id);
      expect(agentIdElement).toHaveClass('truncate');
      expect(agentIdElement).toHaveAttribute('title', longIdWatcher.agent_id);
    });

    it('should handle multiple watchers with same status', () => {
      const sameStatusWatchers: WatcherStatus[] = [
        {
          agent_id: 'agent_a',
          status: 'running',
          last_heartbeat: '2024-01-15T10:00:00Z',
          last_sync: '2024-01-15T09:55:00Z',
          error: null,
        },
        {
          agent_id: 'agent_b',
          status: 'running',
          last_heartbeat: '2024-01-15T10:01:00Z',
          last_sync: '2024-01-15T09:56:00Z',
          error: null,
        },
      ];

      render(<WatcherStatusGrid watchers={sameStatusWatchers} onRefresh={mockOnRefresh} />);

      const runningBadges = screen.getAllByText('running');
      expect(runningBadges.length).toBe(2);
    });

    it('should handle very long error messages', () => {
      const longErrorWatcher: WatcherStatus = {
        agent_id: 'agent_long_error',
        status: 'failed',
        last_heartbeat: '2024-01-15T10:00:00Z',
        last_sync: '2024-01-15T09:55:00Z',
        error: 'This is a very long error message that describes in detail what went wrong with the watcher process and includes technical information',
      };

      render(<WatcherStatusGrid watchers={[longErrorWatcher]} onRefresh={mockOnRefresh} />);

      expect(screen.getByText(longErrorWatcher.error)).toBeInTheDocument();
    });

    it('should handle single watcher', () => {
      const singleWatcher: WatcherStatus[] = [mockWatchers[0]];

      render(<WatcherStatusGrid watchers={singleWatcher} onRefresh={mockOnRefresh} />);

      expect(screen.getByText('agent1')).toBeInTheDocument();
      expect(screen.queryByText('agent2')).not.toBeInTheDocument();
    });
  });

  describe('Responsive Grid Layout', () => {
    it('should apply grid layout classes', () => {
      const { container } = render(
        <WatcherStatusGrid watchers={mockWatchers} onRefresh={mockOnRefresh} />
      );

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3');
    });
  });
});
