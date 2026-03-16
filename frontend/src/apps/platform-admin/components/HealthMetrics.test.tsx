/**
 * Unit tests for HealthMetrics component
 * 
 * **Validates: Requirements 23.4**
 * 
 * Tests cover:
 * - Display of system status with correct styling
 * - Display of database connection status
 * - Display of active watcher count
 * - Display of failed watcher count with warning styling
 * - Display of error count with appropriate styling
 * - Timestamp formatting
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HealthMetrics } from './HealthMetrics';
import { HealthData } from '../pages/DashboardPage';

describe('HealthMetrics', () => {
  const mockHealthData: HealthData = {
    status: 'healthy',
    timestamp: '2024-01-15T10:30:00Z',
    database: 'connected',
    watchers: {
      active: 3,
      failed: 0,
    },
    errors_24h: 5,
  };

  describe('System Status Display', () => {
    it('should display healthy status with green indicator', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('healthy')).toBeInTheDocument();
      expect(screen.getByText('healthy')).toHaveClass('text-green-700');
    });

    it('should display unhealthy status with red indicator', () => {
      const unhealthyData: HealthData = {
        ...mockHealthData,
        status: 'unhealthy',
      };

      render(<HealthMetrics healthData={unhealthyData} />);

      expect(screen.getByText('unhealthy')).toBeInTheDocument();
      expect(screen.getByText('unhealthy')).toHaveClass('text-red-700');
    });

    it('should display status label', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('Status')).toBeInTheDocument();
    });
  });

  describe('Database Status Display', () => {
    it('should display connected database status with green indicator', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('connected')).toBeInTheDocument();
      expect(screen.getByText('connected')).toHaveClass('text-green-700');
    });

    it('should display disconnected database status with red indicator', () => {
      const disconnectedData: HealthData = {
        ...mockHealthData,
        database: 'disconnected',
      };

      render(<HealthMetrics healthData={disconnectedData} />);

      expect(screen.getByText('disconnected')).toBeInTheDocument();
      expect(screen.getByText('disconnected')).toHaveClass('text-red-700');
    });

    it('should display database label', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('Database')).toBeInTheDocument();
    });
  });

  describe('Active Watchers Display', () => {
    it('should display active watcher count', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      const activeWatchersText = screen.getByText('Active Watchers');
      const activeWatchersCard = activeWatchersText.closest('.bg-gray-50');
      
      expect(activeWatchersCard).toBeInTheDocument();
      expect(activeWatchersCard).toHaveTextContent('3');
    });

    it('should display zero active watchers', () => {
      const noWatchersData: HealthData = {
        ...mockHealthData,
        watchers: { active: 0, failed: 0 },
      };

      render(<HealthMetrics healthData={noWatchersData} />);

      const activeWatchersText = screen.getByText('Active Watchers');
      const activeWatchersCard = activeWatchersText.closest('.bg-gray-50');
      
      expect(activeWatchersCard).toBeInTheDocument();
      expect(activeWatchersCard).toHaveTextContent('0');
    });

    it('should display active watchers with blue styling', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      const activeWatchersText = screen.getByText('Active Watchers');
      const activeWatchersCard = activeWatchersText.closest('.bg-gray-50');
      const activeCount = activeWatchersCard?.querySelector('.text-2xl');
      
      expect(activeCount).toHaveClass('text-blue-600');
    });
  });

  describe('Failed Watchers Display', () => {
    it('should display zero failed watchers with gray styling', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      // Find the failed watchers value by looking for the text within the section
      const failedWatchersText = screen.getByText('Failed Watchers');
      const failedWatchersCard = failedWatchersText.closest('.bg-gray-50');
      
      expect(failedWatchersCard).toBeInTheDocument();
      expect(failedWatchersCard).toHaveTextContent('0');
    });

    it('should display failed watchers with red styling when count > 0', () => {
      const failedWatchersData: HealthData = {
        ...mockHealthData,
        watchers: { active: 2, failed: 3 },
      };

      render(<HealthMetrics healthData={failedWatchersData} />);

      const failedWatchersText = screen.getByText('Failed Watchers');
      const failedWatchersCard = failedWatchersText.closest('.bg-gray-50');
      
      expect(failedWatchersCard).toBeInTheDocument();
      expect(failedWatchersCard).toHaveTextContent('3');
    });

    it('should display failed watchers label', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('Failed Watchers')).toBeInTheDocument();
    });
  });

  describe('Errors Display', () => {
    it('should display error count with orange styling when count > 0', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      const errorsText = screen.getByText('Errors (24h)');
      const errorsCard = errorsText.closest('.bg-gray-50');
      
      expect(errorsCard).toBeInTheDocument();
      expect(errorsCard).toHaveTextContent('5');
    });

    it('should display zero errors with gray styling', () => {
      const noErrorsData: HealthData = {
        ...mockHealthData,
        errors_24h: 0,
      };

      render(<HealthMetrics healthData={noErrorsData} />);

      const errorsText = screen.getByText('Errors (24h)');
      const errorsCard = errorsText.closest('.bg-gray-50');
      
      expect(errorsCard).toBeInTheDocument();
      expect(errorsCard).toHaveTextContent('0');
    });

    it('should display errors label', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('Errors (24h)')).toBeInTheDocument();
    });
  });

  describe('Timestamp Display', () => {
    it('should display formatted timestamp', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });

    it('should format timestamp as locale string', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      const timestamp = new Date(mockHealthData.timestamp).toLocaleString();
      expect(screen.getByText(`Last updated: ${timestamp}`)).toBeInTheDocument();
    });
  });

  describe('Component Structure', () => {
    it('should render component title', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('System Health')).toBeInTheDocument();
    });

    it('should render all metric cards', () => {
      render(<HealthMetrics healthData={mockHealthData} />);

      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Database')).toBeInTheDocument();
      expect(screen.getByText('Active Watchers')).toBeInTheDocument();
      expect(screen.getByText('Failed Watchers')).toBeInTheDocument();
      expect(screen.getByText('Errors (24h)')).toBeInTheDocument();
    });

    it('should apply correct styling classes', () => {
      const { container } = render(<HealthMetrics healthData={mockHealthData} />);

      const mainContainer = container.firstChild;
      expect(mainContainer).toHaveClass('bg-white', 'rounded-lg', 'shadow', 'p-6');
    });
  });

  describe('Edge Cases', () => {
    it('should handle large watcher counts', () => {
      const largeCountData: HealthData = {
        ...mockHealthData,
        watchers: { active: 999, failed: 50 },
      };

      render(<HealthMetrics healthData={largeCountData} />);

      expect(screen.getByText('999')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument();
    });

    it('should handle large error counts', () => {
      const largeErrorData: HealthData = {
        ...mockHealthData,
        errors_24h: 1000,
      };

      render(<HealthMetrics healthData={largeErrorData} />);

      expect(screen.getByText('1000')).toBeInTheDocument();
    });

    it('should handle different timestamp formats', () => {
      const differentTimestampData: HealthData = {
        ...mockHealthData,
        timestamp: '2024-12-31T23:59:59Z',
      };

      render(<HealthMetrics healthData={differentTimestampData} />);

      const timestamp = new Date(differentTimestampData.timestamp).toLocaleString();
      expect(screen.getByText(`Last updated: ${timestamp}`)).toBeInTheDocument();
    });
  });
});
