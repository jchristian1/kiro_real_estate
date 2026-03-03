/**
 * Dashboard Page Component
 * 
 * Main dashboard showing system health and watcher status.
 * Polls health endpoint every 5 seconds for real-time updates.
 * 
 * Requirements: 8.5, 8.6, 16.1, 16.2, 16.3
 */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { HealthMetrics } from '../components/HealthMetrics';
import { WatcherStatusGrid } from '../components/WatcherStatusGrid';
import { RecentErrorsTable } from '../components/RecentErrorsTable';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface HealthData {
  status: string;
  timestamp: string;
  database: string;
  watchers: {
    active: number;
    failed: number;
  };
  errors_24h: number;
}

export interface WatcherStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string | null;
  last_sync: string | null;
  error: string | null;
}

export const DashboardPage: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [watcherStatuses, setWatcherStatuses] = useState<WatcherStatus[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch health data from API
   */
  const fetchHealthData = async () => {
    try {
      const response = await axios.get<HealthData>(`${API_BASE_URL}/health`);
      setHealthData(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch health data:', err);
      setError('Failed to load health data');
    }
  };

  /**
   * Fetch watcher statuses from API
   */
  const fetchWatcherStatuses = async () => {
    try {
      const response = await axios.get<{ watchers: WatcherStatus[] }>(`${API_BASE_URL}/watchers/status`);
      setWatcherStatuses(response.data.watchers);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch watcher statuses:', err);
      setError('Failed to load watcher statuses');
    }
  };

  /**
   * Fetch all dashboard data
   */
  const fetchDashboardData = async () => {
    setLoading(true);
    await Promise.all([fetchHealthData(), fetchWatcherStatuses()]);
    setLoading(false);
  };

  /**
   * Set up polling for health data every 5 seconds
   */
  useEffect(() => {
    // Initial fetch
    fetchDashboardData();

    // Set up polling interval
    const intervalId = setInterval(() => {
      fetchHealthData();
      fetchWatcherStatuses();
    }, 5000); // Poll every 5 seconds

    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading dashboard...</div>
      </div>
    );
  }

  if (error && !healthData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>

      {/* Health Metrics Section */}
      {healthData && <HealthMetrics healthData={healthData} />}

      {/* Watcher Status Grid Section */}
      <WatcherStatusGrid watchers={watcherStatuses} onRefresh={fetchWatcherStatuses} />

      {/* Recent Errors Table Section */}
      <RecentErrorsTable errorCount={healthData?.errors_24h || 0} />
    </div>
  );
};
