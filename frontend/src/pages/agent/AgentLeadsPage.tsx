/**
 * Agent Leads Page
 *
 * Shows all leads assigned to the currently logged-in agent.
 * Supports search and status filtering.
 */

import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface Lead {
  id: number;
  name: string | null;
  phone: string | null;
  source_email: string | null;
  gmail_uid: string | null;
  lead_source_id: number | null;
  created_at: string;
  updated_at: string | null;
  response_sent: boolean;
  response_status: string | null;
  agent_id: string | null;
  agent_name: string | null;
  company_id: number | null;
  company_name: string | null;
}

interface LeadsResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

const STATUS_FILTERS = [
  { label: 'Todos', value: '' },
  { label: 'Enviado', value: 'true' },
  { label: 'Pendiente', value: 'false' },
] as const;

const statusBadge = (sent: boolean, status: string | null) => {
  if (sent)
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-full">
        ✅ Enviado
      </span>
    );
  if (status === 'failed')
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full">
        ❌ Fallido
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-amber-100 text-amber-700 rounded-full">
      ⏳ Pendiente
    </span>
  );
};

const formatDate = (dateStr: string) =>
  new Date(dateStr).toLocaleDateString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

export const AgentLeadsPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: '20',
        sort: 'created_at',
        order: 'desc',
      };
      // Filter by the logged-in agent's username
      if (user?.username) params.agent_id = user.username;
      if (statusFilter !== '') params.response_sent = statusFilter;

      const res = await axios.get<LeadsResponse>(`${API_BASE_URL}/leads`, { params });
      let data = res.data.leads;

      // Client-side search filter (name or phone)
      if (search.trim()) {
        const q = search.toLowerCase();
        data = data.filter(
          (l) =>
            l.name?.toLowerCase().includes(q) ||
            l.phone?.toLowerCase().includes(q) ||
            l.source_email?.toLowerCase().includes(q)
        );
      }

      setLeads(data);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
      setFetchError(null);
    } catch {
      setFetchError('No se pudieron cargar los leads. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, search, user]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const clearSearch = () => {
    setSearch('');
    setSearchInput('');
    setPage(1);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mis Leads</h1>
        <p className="text-sm text-gray-500 mt-1">
          Leads asignados a tu cuenta · {total} total
        </p>
      </div>

      {/* Search + Status filter bar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-end">
        <form onSubmit={handleSearch} className="flex-1 flex gap-2">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Buscar
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Nombre, teléfono o email..."
                className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>
          </div>
          <button
            type="submit"
            className="self-end px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Buscar
          </button>
          {search && (
            <button
              type="button"
              onClick={clearSearch}
              className="self-end px-3 py-2 text-gray-500 hover:text-gray-700 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              ✕ Limpiar
            </button>
          )}
        </form>

        <div className="sm:w-48">
          <label className="block text-xs font-medium text-gray-500 mb-1">Estado</label>
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => { setStatusFilter(f.value); setPage(1); }}
                className={`flex-1 text-xs font-medium py-1.5 px-2 rounded-md transition-colors ${statusFilter === f.value
                    ? 'bg-white text-emerald-700 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                  }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Cargando leads...</span>
          </div>
        </div>
      ) : fetchError ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-600 font-medium">{fetchError}</p>
          <button
            onClick={fetchLeads}
            className="mt-3 text-sm text-red-500 underline hover:no-underline"
          >
            Reintentar
          </button>
        </div>
      ) : leads.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <div className="text-5xl mb-3">📭</div>
          <p className="text-gray-500 font-medium">No hay leads{search ? ' con ese criterio de búsqueda' : ' asignados'}</p>
          {search && (
            <button onClick={clearSearch} className="mt-2 text-sm text-emerald-600 underline">
              Limpiar búsqueda
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Leads table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="min-w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Contacto
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Teléfono
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden md:table-cell">
                    Empresa
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                    Fecha
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Estado
                  </th>
                  <th className="px-5 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Acción
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="hover:bg-emerald-50 transition-colors cursor-pointer group"
                    onClick={() => navigate(`/agent/leads/${lead.id}`, { state: { lead } })}
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
                          {lead.name?.[0]?.toUpperCase() ?? '?'}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {lead.name || <span className="text-gray-400 italic">Sin nombre</span>}
                          </p>
                          <p className="text-xs text-gray-400 truncate max-w-[180px]">
                            {lead.source_email || '—'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      {lead.phone ? (
                        <a
                          href={`tel:${lead.phone}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-sm text-emerald-600 hover:text-emerald-800 font-medium hover:underline"
                        >
                          {lead.phone}
                        </a>
                      ) : (
                        <span className="text-sm text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-5 py-4 hidden md:table-cell">
                      <span className="text-sm text-gray-600">{lead.company_name || '—'}</span>
                    </td>
                    <td className="px-5 py-4 hidden lg:table-cell">
                      <span className="text-sm text-gray-500">{formatDate(lead.created_at)}</span>
                    </td>
                    <td className="px-5 py-4">
                      {statusBadge(lead.response_sent, lead.response_status)}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/agent/leads/${lead.id}`, { state: { lead } }); }}
                        className="text-xs font-medium text-emerald-600 hover:text-emerald-800 group-hover:underline"
                      >
                        Ver detalle →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Anterior
              </button>
              <span className="text-sm text-gray-600">
                Página <strong>{page}</strong> de <strong>{totalPages}</strong>
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
