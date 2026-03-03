/**
 * Audit Logs Page Component
 * Requirements: 7.1, 7.2, 7.4
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface AuditLog {
  id: number;
  timestamp: string;
  user_id: number;
  username: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  details: string | null;
}

interface AuditLogsResponse {
  logs: AuditLog[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

interface Filters {
  action: string;
  user_id: string;
  start_date: string;
  end_date: string;
}

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<Filters>({ action: '', user_id: '', start_date: '', end_date: '' });

  const buildParams = useCallback(() => {
    const p: Record<string, string> = { page: String(page), per_page: '100' };
    if (filters.action) p.action = filters.action;
    if (filters.user_id) p.user_id = filters.user_id;
    if (filters.start_date) p.start_date = filters.start_date;
    if (filters.end_date) p.end_date = filters.end_date;
    return p;
  }, [page, filters]);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<AuditLogsResponse>(`${API_BASE_URL}/audit-logs`, { params: buildParams() });
      setLogs(res.data.logs);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
      setFetchError(null);
    } catch {
      setFetchError('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const handleFilter = (key: keyof Filters, val: string) => {
    setFilters((f) => ({ ...f, [key]: val }));
    setPage(1);
  };

  const actionBadgeColor = (action: string) => {
    if (action.includes('created')) return 'bg-green-100 text-green-800';
    if (action.includes('deleted')) return 'bg-red-100 text-red-800';
    if (action.includes('updated') || action.includes('rollback')) return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-700';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Audit Logs <span className="text-sm font-normal text-gray-500">({total})</span></h1>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="audit-filters">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Action</label>
          <input type="text" value={filters.action} onChange={(e) => handleFilter('action', e.target.value)}
            placeholder="e.g. agent_created" className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-action" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">User ID</label>
          <input type="text" value={filters.user_id} onChange={(e) => handleFilter('user_id', e.target.value)}
            placeholder="User ID" className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-user-id" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
          <input type="date" value={filters.start_date} onChange={(e) => handleFilter('start_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-start-date" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
          <input type="date" value={filters.end_date} onChange={(e) => handleFilter('end_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-end-date" />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><span className="text-gray-500">Loading audit logs...</span></div>
      ) : fetchError ? (
        <div className="flex items-center justify-center h-32"><span className="text-red-600">{fetchError}</span></div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500" data-testid="audit-empty">No audit logs found</div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200" data-testid="audit-table">
              <thead className="bg-gray-50">
                <tr>
                  {['Timestamp', 'User', 'Action', 'Resource', 'Details'].map((h) => (
                    <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50" data-testid={`audit-row-${log.id}`}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.username}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${actionBadgeColor(log.action)}`}>{log.action}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {log.resource_type}{log.resource_id ? ` #${log.resource_id}` : ''}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate" title={log.details ?? ''}>{log.details || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between" data-testid="pagination">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
                Previous
              </button>
              <span className="text-sm text-gray-600">Page {page} of {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
