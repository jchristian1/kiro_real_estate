/**
 * Leads Page Component
 * Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 19.5, 19.6
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useToast } from '../contexts/ToastContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface Lead {
  id: number;
  name: string | null;
  phone: string | null;
  source_email: string | null;
  gmail_uid: string | null;
  created_at: string;
  response_sent: boolean;
  response_status: string | null;
}

interface LeadFilters {
  agent_id: string;
  start_date: string;
  end_date: string;
  response_sent: string;
}

interface LeadsResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

type SortField = 'name' | 'created_at' | 'response_sent';
type SortDir = 'asc' | 'desc';

export const LeadsPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<LeadFilters>({ agent_id: '', start_date: '', end_date: '', response_sent: '' });
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [exporting, setExporting] = useState(false);

  const buildParams = useCallback(() => {
    const p: Record<string, string> = { page: String(page), per_page: '50', sort: sortField, order: sortDir };
    if (filters.agent_id) p.agent_id = filters.agent_id;
    if (filters.start_date) p.start_date = filters.start_date;
    if (filters.end_date) p.end_date = filters.end_date;
    if (filters.response_sent !== '') p.response_sent = filters.response_sent;
    return p;
  }, [page, sortField, sortDir, filters]);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get<LeadsResponse>(`${API_BASE_URL}/leads`, { params: buildParams() });
      setLeads(res.data.leads);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
      setFetchError(null);
    } catch {
      setFetchError('Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const handleSort = (field: SortField) => {
    if (field === sortField) setSortDir((d) => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
    setPage(1);
  };

  const handleFilterChange = (key: keyof LeadFilters, val: string) => {
    setFilters((f) => ({ ...f, [key]: val }));
    setPage(1);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = buildParams();
      delete params.page;
      delete params.per_page;
      const res = await axios.get(`${API_BASE_URL}/leads/export`, { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `leads_export_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      success('CSV exported successfully');
    } catch {
      toastError('Failed to export leads');
    } finally {
      setExporting(false);
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => (
    <span className="ml-1 text-gray-400">{sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span>
  );

  const statusBadge = (sent: boolean, status: string | null) => {
    if (sent) return <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full">Sent</span>;
    if (status === 'failed') return <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded-full">Failed</span>;
    return <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">Pending</span>;
  };

  if (selectedLead) {
    return (
      <div className="space-y-6" data-testid="lead-detail">
        <div className="flex items-center gap-4">
          <button onClick={() => setSelectedLead(null)} className="text-sm text-blue-600 hover:text-blue-800">← Back</button>
          <h1 className="text-2xl font-bold text-gray-800">Lead Detail</h1>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <dl className="grid grid-cols-2 gap-4">
            {[
              ['ID', selectedLead.id],
              ['Name', selectedLead.name || '—'],
              ['Phone', selectedLead.phone || '—'],
              ['Source Email', selectedLead.source_email || '—'],
              ['Gmail UID', selectedLead.gmail_uid || '—'],
              ['Created', new Date(selectedLead.created_at).toLocaleString()],
              ['Response Sent', selectedLead.response_sent ? 'Yes' : 'No'],
              ['Response Status', selectedLead.response_status || '—'],
            ].map(([label, val]) => (
              <div key={String(label)}>
                <dt className="text-xs text-gray-500 uppercase tracking-wide">{label}</dt>
                <dd className="mt-1 text-sm text-gray-900">{String(val)}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Leads <span className="text-sm font-normal text-gray-500">({total})</span></h1>
        <button onClick={handleExport} disabled={exporting}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
          data-testid="export-btn">
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="lead-filters">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Agent ID</label>
          <input type="text" value={filters.agent_id} onChange={(e) => handleFilterChange('agent_id', e.target.value)}
            placeholder="Filter by agent" className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-agent-id" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
          <input type="date" value={filters.start_date} onChange={(e) => handleFilterChange('start_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-start-date" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
          <input type="date" value={filters.end_date} onChange={(e) => handleFilterChange('end_date', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-end-date" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Response</label>
          <select value={filters.response_sent} onChange={(e) => handleFilterChange('response_sent', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="filter-response">
            <option value="">All</option>
            <option value="true">Sent</option>
            <option value="false">Not Sent</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><span className="text-gray-500">Loading leads...</span></div>
      ) : fetchError ? (
        <div className="flex items-center justify-center h-32"><span className="text-red-600">{fetchError}</span></div>
      ) : leads.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500" data-testid="leads-empty">No leads found</div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200" data-testid="leads-table">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer" onClick={() => handleSort('name')}>
                    Name <SortIcon field="name" />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer" onClick={() => handleSort('created_at')}>
                    Created <SortIcon field="created_at" />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer" onClick={() => handleSort('response_sent')}>
                    Status <SortIcon field="response_sent" />
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-gray-50" data-testid={`lead-row-${lead.id}`}>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{lead.name || '—'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{lead.phone || '—'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{lead.source_email || '—'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{new Date(lead.created_at).toLocaleDateString()}</td>
                    <td className="px-6 py-4">{statusBadge(lead.response_sent, lead.response_status)}</td>
                    <td className="px-6 py-4 text-right">
                      <button onClick={() => setSelectedLead(lead)} className="text-blue-600 hover:text-blue-900 text-sm" data-testid={`view-lead-${lead.id}`}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
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
