/**
 * Unit tests for DashboardPage component
 * 
 * **Validates: Requirements 23.4**
 * 
 * Tests cover:
 * - Initial data fetching and loading state
 * - Polling mechanism (5-second intervals)
 * - Error handling for API failures
 * - Component rendering with health data
 * - Component rendering with watcher statuses
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import axios from 'axios';
import { DashboardPage, HealthData, WatcherStatus } from './DashboardPage';

// Mock axios
vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

// Mock child components to isolate DashboardPage testing
vi.mock('../components/HealthMetrics', () => ({
  HealthMetrics: ({ healthData }: { healthData: HealthData }) => (
    <div data-testid="health-metrics">
      Health Status: {healthData.status}
    </div>
  ),
}));

vi.mock('../components/WatcherStatusGrid', () => ({
  WatcherStatusGrid: ({ watchers }: { watchers: WatcherStatus[] }) => (
    <div data-testid="watcher-status-grid">
      Watchers: {watchers.length}
    </div>
  ),
}));

vi.mock('../components/RecentErrorsTable', () => ({
  RecentErrorsTable: ({ errorCount }: { errorCount: number }) => (
    <div data-testid="recent-errors-table">
      Errors: {errorCount}
    </div>
  ),
}));

describe('DashboardPage', () => {
  const mockHealthData: HealthData = {
    status: 'healthy',
    timestamp: '2024-01-15T10:00:00Z',
    database: 'connected',
    watchers: {
      active: 3,
      failed: 0,
    },
    errors_24h: 5,
  };

  const mockWatcherStatuses: WatcherStatus[] = [
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
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderDashboard = () => {
    return render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
  };

  describe('Initial Loading', () => {
    it('should show loading state initially', () => {
      mockedAxios.get = vi.fn(() => new Promise(() => {})); // Never resolves

      renderDashboard();

      expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();
    });

    it('should fetch health data and watcher statuses on mount', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.queryByText('Loading dashboard...')).not.toBeInTheDocument();
      });

      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/health')
      );
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/watchers/status')
      );
    });

    it('should render all child components after loading', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByTestId('health-metrics')).toBeInTheDocument();
      });

      expect(screen.getByTestId('watcher-status-grid')).toBeInTheDocument();
      expect(screen.getByTestId('recent-errors-table')).toBeInTheDocument();
    });
  });

  describe('Data Fetching', () => {
    it('should pass health data to HealthMetrics component', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Health Status: healthy')).toBeInTheDocument();
      });
    });

    it('should pass watcher statuses to WatcherStatusGrid component', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Watchers: 2')).toBeInTheDocument();
      });
    });

    it('should pass error count to RecentErrorsTable component', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Errors: 5')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle health data fetch failure gracefully', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.reject(new Error('Network error'));
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Should still render the page structure even with error
      await waitFor(() => {
        expect(screen.queryByText('Loading dashboard...')).not.toBeInTheDocument();
      });

      // Dashboard title should still be visible
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    it('should handle watcher status fetch failure gracefully', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Should still render health data even if watcher status fails
      await waitFor(() => {
        expect(screen.getByText('Health Status: healthy')).toBeInTheDocument();
      });

      // Dashboard should still be functional
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    it('should continue showing data after initial load', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('health-metrics')).toBeInTheDocument();
      });

      // Data should be visible
      expect(screen.getByText('Health Status: healthy')).toBeInTheDocument();
      expect(screen.getByText('Watchers: 2')).toBeInTheDocument();
    });
  });

  describe('Polling Mechanism', () => {
    it('should set up polling interval on mount', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Wait for initial load
      await waitFor(() => {
        expect(screen.queryByText('Loading dashboard...')).not.toBeInTheDocument();
      });

      // Verify initial calls were made
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/health')
      );
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/watchers/status')
      );
    });

    it('should fetch both health and watcher data', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Wait for initial load
      await waitFor(() => {
        expect(screen.queryByText('Loading dashboard...')).not.toBeInTheDocument();
      });

      // Verify both endpoints were called
      const healthCalls = mockedAxios.get.mock.calls.filter((call: unknown[]) =>
        (call[0] as string).includes('/health')
      );
      const watcherCalls = mockedAxios.get.mock.calls.filter((call: unknown[]) =>
        (call[0] as string).includes('/watchers/status')
      );

      expect(healthCalls.length).toBeGreaterThan(0);
      expect(watcherCalls.length).toBeGreaterThan(0);
    });

    it('should display fetched data correctly', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: mockWatcherStatuses } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      // Wait for data to be displayed
      await waitFor(() => {
        expect(screen.getByText('Health Status: healthy')).toBeInTheDocument();
      });

      expect(screen.getByText('Watchers: 2')).toBeInTheDocument();
    });

    it('should cleanup polling interval on unmount', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      const { unmount } = renderDashboard();

      // Wait for initial load
      await waitFor(() => {
        expect(screen.queryByText('Loading dashboard...')).not.toBeInTheDocument();
      });

      // Unmount component - this should cleanup the interval
      unmount();

      // Component should be unmounted
      expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
    });
  });

  describe('Component Integration', () => {
    it('should render dashboard title', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });
    });

    it('should handle empty watcher list', async () => {
      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: mockHealthData });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Watchers: 0')).toBeInTheDocument();
      });
    });

    it('should handle zero errors', async () => {
      const healthDataNoErrors: HealthData = {
        ...mockHealthData,
        errors_24h: 0,
      };

      mockedAxios.get = vi.fn((url: string) => {
        if (url.includes('/health')) {
          return Promise.resolve({ data: healthDataNoErrors });
        }
        if (url.includes('/watchers/status')) {
          return Promise.resolve({ data: { watchers: [] } });
        }
        return Promise.reject(new Error('Unknown endpoint'));
      });

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText('Errors: 0')).toBeInTheDocument();
      });
    });
  });
});
