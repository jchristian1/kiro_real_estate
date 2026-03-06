/**
 * Agent Lead Detail Page
 * 
 * Shows detailed information about a specific lead.
 * Currently shows basic information since backend doesn't have all fields yet.
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Lead } from './AgentLeadsPage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// For now, use the same Lead interface since the backend doesn't have additional fields
interface LeadDetail extends Lead {
  // These fields will be added when the backend supports them
  // notes?: string | null;
  // last_contacted?: string | null;
  // follow_up_date?: string | null;
  // priority?: 'low' | 'medium' | 'high' | null;
  // tags?: string[] | null;
  // communication_history?: Communication[];
}

export const AgentLeadDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sendingResponse, setSendingResponse] = useState(false);

  // Try to get lead from navigation state first (for faster loading)
  useEffect(() => {
    if (location.state?.lead) {
      setLead(location.state.lead);
    }
  }, [location.state]);

  useEffect(() => {
    const fetchLeadDetail = async () => {
      if (!id) return;
      
      setLoading(true);
      try {
        const response = await axios.get<LeadDetail>(`${API_BASE_URL}/leads/${id}`);
        setLead(response.data);
        setError(null);
      } catch (err) {
        setError('No se pudo cargar la información del lead. Intenta de nuevo.');
        console.error('Error fetching lead detail:', err);
      } finally {
        setLoading(false);
      }
    };

    // Only fetch if we don't have the lead from navigation state
    if (!location.state?.lead) {
      fetchLeadDetail();
    } else {
      setLoading(false);
    }
  }, [id, location.state]);

  const handleSendResponse = async () => {
    if (!lead || !id) return;
    
    setSendingResponse(true);
    try {
      // TODO: Implement this endpoint in the backend
      alert('Esta funcionalidad estará disponible pronto cuando se implemente el endpoint en el backend');
    } catch (err) {
      console.error('Error sending response:', err);
      alert('Error al enviar la respuesta');
    } finally {
      setSendingResponse(false);
    }
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading && !lead) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Cargando información del lead...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-red-600 font-medium">{error}</p>
          <button
            onClick={() => navigate('/agent/leads')}
            className="mt-3 text-sm text-red-500 underline hover:no-underline"
          >
            Volver a la lista de leads
          </button>
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <div className="text-5xl mb-3">🔍</div>
          <p className="text-gray-500 font-medium">Lead no encontrado</p>
          <button
            onClick={() => navigate('/agent/leads')}
            className="mt-4 text-sm text-emerald-600 underline hover:no-underline"
          >
            Volver a la lista de leads
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header with back button */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/agent/leads')}
            className="text-gray-500 hover:text-gray-700"
          >
            ← Volver
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {lead.name || 'Lead sin nombre'}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              ID: {lead.id} · Creado el {new Date(lead.created_at).toLocaleDateString('es-ES')}
            </p>
          </div>
        </div>
        
        <div className="flex gap-2">
          {!lead.response_sent && (
            <button
              onClick={handleSendResponse}
              disabled={sendingResponse}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sendingResponse ? 'Enviando...' : '📤 Enviar respuesta'}
            </button>
          )}
          <button
            onClick={() => window.print()}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
          >
            🖨️ Imprimir
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Lead information */}
        <div className="lg:col-span-2 space-y-6">
          {/* Contact card */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Información de contacto</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Nombre</label>
                <p className="text-sm text-gray-900 font-medium">
                  {lead.name || <span className="text-gray-400 italic">No especificado</span>}
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Teléfono</label>
                {lead.phone ? (
                  <a
                    href={`tel:${lead.phone}`}
                    className="text-sm text-emerald-600 hover:text-emerald-800 font-medium hover:underline"
                  >
                    {lead.phone}
                  </a>
                ) : (
                  <p className="text-sm text-gray-400 italic">No especificado</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Email de origen</label>
                <p className="text-sm text-gray-900">{lead.source_email || '—'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Empresa</label>
                <p className="text-sm text-gray-900">{lead.company_name || '—'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Estado de respuesta</label>
                <div className="mt-1">
                  {lead.response_sent ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-full">
                      ✅ Enviado
                    </span>
                  ) : lead.response_status === 'failed' ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full">
                      ❌ Fallido
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold bg-amber-100 text-amber-700 rounded-full">
                      ⏳ Pendiente
                    </span>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Agente asignado</label>
                <p className="text-sm text-gray-900">{lead.agent_name || user?.username || '—'}</p>
              </div>
            </div>
          </div>

          {/* Notes card - Will be available when backend supports notes */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Notas y seguimiento</h2>
            <p className="text-sm text-gray-500 mb-4">
              Esta funcionalidad estará disponible pronto cuando el backend soporte el almacenamiento de notas.
            </p>
            <textarea
              disabled
              placeholder="Las notas estarán disponibles en una futura actualización..."
              className="w-full h-40 p-3 border border-gray-300 rounded-lg text-sm bg-gray-50 text-gray-400 resize-none"
            />
          </div>
        </div>

        {/* Right column: Actions and metadata */}
        <div className="space-y-6">
          {/* Quick actions */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Acciones rápidas</h2>
            <div className="space-y-2">
              {lead.phone && (
                <a
                  href={`tel:${lead.phone}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  📞 Llamar ahora
                </a>
              )}
              <button
                onClick={() => window.open(`mailto:${lead.source_email || ''}`, '_blank')}
                disabled={!lead.source_email}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                📧 Enviar email
              </button>
              <button
                onClick={() => window.open(`https://calendar.google.com/calendar/render?action=TEMPLATE&text=Reunión+con+${encodeURIComponent(lead.name || 'Lead')}&details=Follow-up+lead+${lead.id}`, '_blank')}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                📅 Agendar reunión
              </button>
              <button
                onClick={() => navigator.clipboard.writeText(`${lead.name || 'Lead'} - ${lead.phone || 'Sin teléfono'} - ${lead.source_email || 'Sin email'}`)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                📋 Copiar información
              </button>
            </div>
          </div>

          {/* Metadata */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Información del sistema</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">ID del lead</label>
                <p className="text-sm text-gray-900 font-mono">{lead.id}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Gmail UID</label>
                <p className="text-sm text-gray-900 font-mono truncate">{lead.gmail_uid || '—'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Creado</label>
                <p className="text-sm text-gray-900">{formatDateTime(lead.created_at)}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Lead Source ID</label>
                <p className="text-sm text-gray-900">{lead.lead_source_id || '—'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Company ID</label>
                <p className="text-sm text-gray-900">{lead.company_id || '—'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};