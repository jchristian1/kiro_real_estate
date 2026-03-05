/**
 * LeadStatesTab — paginated leads table with current_state, funnel chart.
 * Requirements: 14.1, 14.2, 14.3, 14.4
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface LeadStateRow {
  id: number;
  name: string | null;
  current_state: string | null;
  current_state_updated_at: string | null;
  bucket: string | null;
}

interface LeadsStateResponse {
  leads: LeadStateRow[];
  total: number;
  page: number;
  pages: number;
}

interface FunnelEntry { state: string; count: number; }

const STATE_OPTIONS = [
  'NEW',
  'FORM_INVITE_CREATED',
  'FORM_INVITE_SENT',
  'FORM_SUBMITTED',
  'SCORED',
  'POST_SUBMISSION_EMAIL_SENT',
  'DISQUALIFIED',
  'ARCHIVED',
];

const BUCKET_OPTIONS = ['HOT', 'WARM', 'NURTURE'];

const bucketColor = (bucket: string | null) => {
  if (bucket === 'HOT') return 'bg-red-100 text-red-700';
  if (bucket === 'WARM') return 'bg-yellow-100 text-yellow-700';
  if (bucket === 'NURTURE') return 'bg-blue-100 text-blue-700';
  return 'bg-gray-100 text-gray-500';
};

export const LeadStatesTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();

  const [leads, setLeads] = useState<LeadStateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [stateFilter, setStateFilter] = useState('');
  const [bucketFilter, setBucketFilter] = useState('');

  const [funnel, setFunnel] = useState<FunnelEntry[]>([]);
  const [funnelLoading, setFunnelLoading] = useState(true);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page), per_page: '25' };
      if (stateFilter) params.state = stateFilter;
      if (bucketFilter) params.bucket = bucketFilter;
      const res = await axios.get<LeadsStateResponse>(
        `${API}/buyer-leads/tenants/${tenantId}/leads/states`,
        { params }
      );
      setLeads(res.data.leads);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
    } catch {
      toastError('Failed to load lead states');
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, stateFilter, bucketFilter]);

  const fetchFunnel = useCallback(async () => {
    setFunnelLoading(true);
    try {
      const res = await axios.get<FunnelEntry[]>(
        `${API}/buyer-leads/tenants/${tenantId}/leads/funnel`
      );
      setFunnel(res.data);
    } catch {
      // funnel is non-critical
    } finally {
      setFunnelLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);
  useEffect(() => { fetchFunnel(); }, [fetchFunnel]);

  const maxCount = funnel.reduce((m, e) => Math.max(m, e.count), 1);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-700">Lead States</h2>

      {/* Funnel chart */}
      {!funnelLoading && funnel.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">State Funnel</h3>
          <div className="space-y-2">
            {funnel.map((entry) => (
              <div key={entry.state} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-48 truncate">{entry.state}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div
                    className="bg-blue-500 h-4 rounded-full transition-all"
                    style={{ width: `${(entry.count / maxCount) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-700 w-8 text-right">{entry.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 flex gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">State</label>
          <select
            value={stateFilter}
            onChange={(e) => { setStateFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All States</option>
            {STATE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Bucket</label>
          <select
            value={bucketFilter}
            onChange={(e) => { setBucketFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Buckets</option>
            {BUCKET_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div className="flex items-end">
          <span className="text-sm text-gray-500">{total} leads</span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading…</div>
        ) : leads.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No leads found</div>
        ) : (
          <table className="min-w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lead</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bucket</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{lead.name || `Lead #${lead.id}`}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{lead.current_state || '—'}</td>
                  <td className="px-4 py-3">
                    {lead.bucket ? (
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${bucketColor(lead.bucket)}`}>
                        {lead.bucket}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {lead.current_state_updated_at
                      ? new Date(lead.current_state_updated_at).toLocaleString()
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
