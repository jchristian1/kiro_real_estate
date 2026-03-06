/**
 * BuyerAuditTab — filterable, paginated audit log.
 * Requirements: 16.1, 16.2, 16.3
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useToast } from '../../contexts/ToastContext';

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface AuditEntry {
  id: number;
  lead_id: number | null;
  event_type: string;
  actor_type?: string;
  occurred_at: string;
  metadata_json?: string;
}

interface AuditResponse {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

const EVENT_TYPES = [
  'STATE_TRANSITION',
  'FORM_INVITE_SENT',
  'FORM_SUBMITTED',
  'SCORE_COMPUTED',
  'EMAIL_SENT',
  'EMAIL_FAILED',
];

export const BuyerAuditTab: React.FC = () => {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { error: toastError } = useToast();

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const [leadIdFilter, setLeadIdFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [expandedEntry, setExpandedEntry] = useState<number | null>(null);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page), page_size: '25' };
      if (leadIdFilter) params.lead_id = leadIdFilter;
      if (eventTypeFilter) params.event_type = eventTypeFilter;
      if (startDate) params.date_from = startDate;
      if (endDate) params.date_to = endDate;

      const res = await axios.get<AuditResponse>(
        `${API}/buyer-leads/tenants/${tenantId}/audit`,
        { params }
      );
      setEntries(res.data.items);
      const pages = Math.max(1, Math.ceil(res.data.total / 25));
      setTotalPages(pages);
      setTotal(res.data.total);
    } catch {
      toastError('Failed to load audit log');
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, leadIdFilter, eventTypeFilter, startDate, endDate]);

  useEffect(() => { fetchAudit(); }, [fetchAudit]);

  const handleFilterChange = () => setPage(1);

  const actorBadge = (actor: string) => {
    const colors: Record<string, string> = {
      SYSTEM: 'bg-gray-100 text-gray-600',
      AGENT: 'bg-blue-100 text-blue-700',
      LEAD: 'bg-green-100 text-green-700',
    };
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[actor] ?? 'bg-gray-100 text-gray-600'}`}>
        {actor}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-700">Audit Log</h2>
        <span className="text-sm text-gray-500">{total} entries</span>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Lead ID</label>
          <input
            type="number"
            value={leadIdFilter}
            onChange={(e) => { setLeadIdFilter(e.target.value); handleFilterChange(); }}
            placeholder="Any"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Event Type</label>
          <select
            value={eventTypeFilter}
            onChange={(e) => { setEventTypeFilter(e.target.value); handleFilterChange(); }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Events</option>
            {EVENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); handleFilterChange(); }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); handleFilterChange(); }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading…</div>
        ) : entries.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No audit entries found</div>
        ) : (
          <table className="min-w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actor</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lead ID</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((entry) => (
                <React.Fragment key={entry.id}>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {new Date(entry.occurred_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-800">{entry.event_type}</td>
                    <td className="px-4 py-3">{entry.actor_type ? actorBadge(entry.actor_type) : <span className="text-gray-400 text-xs">—</span>}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{entry.lead_id ?? '—'}</td>
                    <td className="px-4 py-3 text-right">
                      {entry.metadata_json && (
                        <button
                          onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                          className="text-blue-600 hover:text-blue-800 text-xs"
                        >
                          {expandedEntry === entry.id ? 'Hide' : 'Show'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expandedEntry === entry.id && entry.metadata_json && (
                    <tr className="bg-gray-50">
                      <td colSpan={5} className="px-6 py-3">
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                          {JSON.stringify(JSON.parse(entry.metadata_json), null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
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
