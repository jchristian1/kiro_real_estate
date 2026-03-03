/**
 * RegexVersionHistory Component
 *
 * Displays version history for a lead source's regex profile.
 * Allows rolling back to a previous version with a confirmation dialog.
 *
 * Requirements: 9.5, 9.6
 */

import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from './ConfirmDialog';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface RegexProfileVersion {
  version: number;
  name_regex: string;
  phone_regex: string;
  identifier_snippet: string;
  created_at: string;
  created_by: number;
}

export interface RegexVersionHistoryProps {
  leadSourceId: number;
  leadSourceName: string;
  onClose: () => void;
  onRollbackSuccess: () => void;
}

export const RegexVersionHistory: React.FC<RegexVersionHistoryProps> = ({
  leadSourceId,
  leadSourceName,
  onClose,
  onRollbackSuccess,
}) => {
  const [versions, setVersions] = useState<RegexProfileVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<RegexProfileVersion | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        setLoading(true);
        const res = await axios.get<{ versions: RegexProfileVersion[] }>(
          `${API_BASE_URL}/lead-sources/${leadSourceId}/versions`
        );
        setVersions(res.data.versions);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch version history:', err);
        setError('Failed to load version history');
      } finally {
        setLoading(false);
      }
    };

    fetchVersions();
  }, [leadSourceId]);

  const handleRollbackConfirm = async () => {
    if (!rollbackTarget) return;
    setRollbackLoading(true);
    setRollbackError(null);

    try {
      await axios.post(`${API_BASE_URL}/lead-sources/${leadSourceId}/rollback`, {
        version: rollbackTarget.version,
      });
      setRollbackTarget(null);
      onRollbackSuccess();
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string; detail?: string }>;
      const msg =
        axiosError.response?.data?.message ||
        axiosError.response?.data?.detail ||
        'Failed to rollback to selected version';
      setRollbackError(msg);
      setRollbackTarget(null);
    } finally {
      setRollbackLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center"
      data-testid="regex-version-history"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-40"
        onClick={onClose}
        data-testid="version-history-backdrop"
      />

      {/* Panel */}
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 z-10 flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold text-gray-900" data-testid="version-history-title">
              Version History
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">{leadSourceName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
            aria-label="Close version history"
            data-testid="version-history-close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-4">
          {rollbackError && (
            <div
              className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm"
              role="alert"
              data-testid="rollback-error"
            >
              {rollbackError}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center h-32" data-testid="version-history-loading">
              <span className="text-gray-500 text-sm">Loading version history...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-32" data-testid="version-history-error">
              <span className="text-red-600 text-sm">{error}</span>
            </div>
          ) : versions.length === 0 ? (
            <div className="flex items-center justify-center h-32" data-testid="version-history-empty">
              <span className="text-gray-500 text-sm">No version history available</span>
            </div>
          ) : (
            <ul className="space-y-3" data-testid="version-list">
              {versions.map((v, idx) => {
                const isLatest = idx === 0;
                const isExpanded = expandedVersion === v.version;

                return (
                  <li
                    key={v.version}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                    data-testid={`version-item-${v.version}`}
                  >
                    {/* Version header row */}
                    <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-gray-900">
                          Version {v.version}
                        </span>
                        {isLatest && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">
                            Current
                          </span>
                        )}
                        <span className="text-xs text-gray-500">
                          {new Date(v.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setExpandedVersion(isExpanded ? null : v.version)}
                          className="text-xs text-gray-500 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
                          data-testid={`toggle-version-${v.version}`}
                        >
                          {isExpanded ? 'Hide' : 'Details'}
                        </button>
                        {!isLatest && (
                          <button
                            onClick={() => setRollbackTarget(v)}
                            disabled={rollbackLoading}
                            className="text-xs font-medium text-blue-600 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1 disabled:opacity-50 disabled:cursor-not-allowed"
                            data-testid={`rollback-button-${v.version}`}
                          >
                            Rollback
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="px-4 py-3 border-t border-gray-200 space-y-2" data-testid={`version-details-${v.version}`}>
                        <div>
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                            Identifier Snippet
                          </span>
                          <code className="block mt-1 text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded font-mono break-all">
                            {v.identifier_snippet}
                          </code>
                        </div>
                        <div>
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                            Name Regex
                          </span>
                          <code className="block mt-1 text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded font-mono break-all">
                            {v.name_regex}
                          </code>
                        </div>
                        <div>
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                            Phone Regex
                          </span>
                          <code className="block mt-1 text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded font-mono break-all">
                            {v.phone_regex}
                          </code>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Close
          </button>
        </div>
      </div>

      {/* Rollback confirmation dialog */}
      <ConfirmDialog
        isOpen={rollbackTarget !== null}
        title="Rollback Regex Profile"
        message={`Are you sure you want to rollback "${leadSourceName}" to version ${rollbackTarget?.version}? The current configuration will be replaced.`}
        confirmLabel="Rollback"
        onConfirm={handleRollbackConfirm}
        onCancel={() => setRollbackTarget(null)}
      />
    </div>
  );
};
