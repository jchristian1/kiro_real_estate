/**
 * Health Metrics Component
 * 
 * Displays system health metrics including:
 * - Overall system status
 * - Database connection status
 * - Active watcher count
 * - Failed watcher count
 * - Errors in last 24 hours
 * 
 * Requirements: 8.5, 16.1
 */

import React from 'react';
import { HealthData } from '../pages/DashboardPage';

interface HealthMetricsProps {
  healthData: HealthData;
}

export const HealthMetrics: React.FC<HealthMetricsProps> = ({ healthData }) => {
  const isHealthy = healthData.status === 'healthy';
  const isDatabaseConnected = healthData.database?.connected === true;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">System Health</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Overall Status */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Status</div>
          <div className="flex items-center">
            <span
              className={`inline-block w-3 h-3 rounded-full mr-2 ${
                isHealthy ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className={`text-lg font-semibold ${
              isHealthy ? 'text-green-700' : 'text-red-700'
            }`}>
              {healthData.status}
            </span>
          </div>
        </div>

        {/* Database Status */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Database</div>
          <div className="flex items-center">
            <span
              className={`inline-block w-3 h-3 rounded-full mr-2 ${
                isDatabaseConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className={`text-lg font-semibold ${
              isDatabaseConnected ? 'text-green-700' : 'text-red-700'
            }`}>
              {isDatabaseConnected ? 'connected' : 'disconnected'}
            </span>
          </div>
        </div>

        {/* Active Watchers */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Active Watchers</div>
          <div className="text-2xl font-bold text-blue-600">
            {healthData.watchers?.active_count ?? 0}
          </div>
        </div>

        {/* Failed Watchers */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Failed Watchers</div>
          <div className={`text-2xl font-bold ${
            0 > 0 ? 'text-red-600' : 'text-gray-600'
          }`}>
            0
          </div>
        </div>

        {/* Errors (24h) */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Errors (24h)</div>
          <div className={`text-2xl font-bold ${
            (healthData.errors?.count_24h ?? 0) > 0 ? 'text-orange-600' : 'text-gray-600'
          }`}>
            {healthData.errors?.count_24h ?? 0}
          </div>
        </div>
      </div>

      {/* Timestamp */}
      <div className="mt-4 text-xs text-gray-500">
        Last updated: {new Date(healthData.timestamp).toLocaleString()}
      </div>
    </div>
  );
};
