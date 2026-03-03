/**
 * Recent Errors Table Component
 * 
 * Displays errors from the last 24 hours.
 * Shows error count and provides link to full audit logs.
 * 
 * Requirements: 8.6, 16.3
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';

interface RecentErrorsTableProps {
  errorCount: number;
}

export const RecentErrorsTable: React.FC<RecentErrorsTableProps> = ({ errorCount }) => {
  const navigate = useNavigate();

  const handleViewAuditLogs = () => {
    navigate('/audit-logs');
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800">Recent Errors (24h)</h2>
        <button
          onClick={handleViewAuditLogs}
          className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
        >
          View Audit Logs
        </button>
      </div>

      <div className="flex items-center justify-center py-8">
        {errorCount === 0 ? (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-3">
              <svg
                className="w-8 h-8 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div className="text-lg font-medium text-gray-800">No errors in the last 24 hours</div>
            <div className="text-sm text-gray-500 mt-1">System is running smoothly</div>
          </div>
        ) : (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-orange-100 rounded-full mb-3">
              <svg
                className="w-8 h-8 text-orange-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="text-lg font-medium text-gray-800">
              {errorCount} {errorCount === 1 ? 'error' : 'errors'} detected
            </div>
            <div className="text-sm text-gray-500 mt-1">
              Click "View Audit Logs" to see details
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
