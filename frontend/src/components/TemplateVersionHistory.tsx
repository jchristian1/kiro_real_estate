/**
 * TemplateVersionHistory Component
 * Requirements: 3.6, 3.7
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { ConfirmDialog } from './ConfirmDialog';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface TemplateVersion {
  version: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  created_by: number;
}

export interface TemplateVersionHistoryProps {
  templateId: number;
  templateName: string;
  onClose: () => void;
  onRollbackSuccess: () => void;
}

export const TemplateVersionHistory: React.FC<TemplateVersionHistoryProps> = ({
  templateId, templateName, onClose, onRollbackSuccess,
}) => {
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<TemplateVersion | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    axios.get<{ versions: TemplateVersion[] }>(`${API_BASE_URL}/templates/${templateId}/versions`)
      .then((r) => setVersions(r.data.versions))
      .catch(() => setError('Failed to load version history'))
      .finally(() => setLoading(false));
  }, [templateId]);

  const handleRollback = async () => {
    if (!rollbackTarget) return;
    setRollbackLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/templates/${templateId}/rollback`, { version: rollbackTarget.version });
      setRollbackTarget(null);
      onRollbackSuccess();
    } catch (err) {
      const e = err as AxiosError<{ message?: string; detail?: string }>;
      setRollbackError(e.response?.data?.message || e.response?.data?.detail || 'Rollback failed');
      setRollbackTarget(null);
    } finally {
      setRollbackLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center" data-testid="template-version-history">
      <div className="absolute inset-0 bg-black bg-opacity-40" onClick={onClose} data-testid="version-history-backdrop" />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 z-10 flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold text-gray-900" data-testid="version-history-title">Version History</h2>
            <p className="text-sm text-gray-500 mt-0.5">{templateName}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500" aria-label="Close" data-testid="version-history-close">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-4">
          {rollbackError && <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm" role="alert" data-testid="rollback-error">{rollbackError}</div>}
          {loading && <div className="flex items-center justify-center h-32" data-testid="version-history-loading"><span className="text-gray-500 text-sm">Loading...</span></div>}
          {error && <div className="flex items-center justify-center h-32" data-testid="version-history-error"><span className="text-red-600 text-sm">{error}</span></div>}
          {!loading && !error && versions.length === 0 && <div className="flex items-center justify-center h-32" data-testid="version-history-empty"><span className="text-gray-500 text-sm">No version history</span></div>}
          {!loading && !error && versions.length > 0 && (
            <ul className="space-y-3" data-testid="version-list">
              {versions.map((v, idx) => {
                const isLatest = idx === 0;
                const isExpanded = expanded === v.version;
                return (
                  <li key={v.version} className="border border-gray-200 rounded-lg overflow-hidden" data-testid={`version-item-${v.version}`}>
                    <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-gray-900">Version {v.version}</span>
                        {isLatest && <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">Current</span>}
                        <span className="text-xs text-gray-500">{new Date(v.created_at).toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => setExpanded(isExpanded ? null : v.version)} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded focus:outline-none" data-testid={`toggle-version-${v.version}`}>{isExpanded ? 'Hide' : 'Details'}</button>
                        {!isLatest && <button onClick={() => setRollbackTarget(v)} disabled={rollbackLoading} className="text-xs font-medium text-blue-600 hover:text-blue-800 px-2 py-1 rounded focus:outline-none disabled:opacity-50" data-testid={`rollback-button-${v.version}`}>Rollback</button>}
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="px-4 py-3 border-t border-gray-200 space-y-2" data-testid={`version-details-${v.version}`}>
                        <div><span className="text-xs font-medium text-gray-500 uppercase">Subject</span><p className="mt-1 text-sm text-gray-700">{v.subject}</p></div>
                        <div><span className="text-xs font-medium text-gray-500 uppercase">Body</span><pre className="mt-1 text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded whitespace-pre-wrap font-sans">{v.body}</pre></div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">Close</button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={rollbackTarget !== null}
        title="Rollback Template"
        message={`Roll back "${templateName}" to version ${rollbackTarget?.version}? The current version will be replaced.`}
        confirmLabel="Rollback"
        onConfirm={handleRollback}
        onCancel={() => setRollbackTarget(null)}
      />
    </div>
  );
};
