import React from 'react';
import { useT } from "@/shared/hooks/useT";
import { MockLead } from '../../mockData';
import { getCalledStatusColor, getTextedStatusColor } from '../LeadsLawDrawerRight';

interface LeadsLawTableProps {
  data: MockLead[];
  onSelectLeadLeft: (lead: MockLead) => void;
  onSelectLeadRight: (lead: MockLead) => void;
  activeLeadIdLeft?: string | null;
  activeLeadIdRight?: string | null;
}

export const LeadsLawTable: React.FC<LeadsLawTableProps> = ({ data, onSelectLeadLeft, onSelectLeadRight, activeLeadIdLeft, activeLeadIdRight }) => {
  const t = useT() as any;

  return (
    <div style={{ ...t.card, overflowX: "auto" }} data-testid="leads-table">
      <div style={{ minWidth: 1600 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th colSpan={6} style={{ background: 'rgba(239, 68, 68, 0.1)', color: t.red, padding: '12px 16px', fontSize: 20, fontWeight: 900, textAlign: 'center', textTransform: 'uppercase', border: `1px solid ${t.border}`, borderBottom: 'none', borderRight: `1px solid ${t.textMuted}` }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ background: t.red, color: '#fff', width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 'bold' }}>✖</div>
                  ISSUE
                </span>
              </th>
              <th colSpan={8} style={{ background: 'rgba(34, 197, 94, 0.15)', color: '#064e3b', padding: '12px 16px', fontSize: 20, fontWeight: 900, textAlign: 'center', border: `1px solid ${t.border}`, borderBottom: 'none', letterSpacing: '1px' }}>
                RETAINER PROCESSING
              </th>
            </tr>
            <tr>
              {['   ', 'Full Name', 'Phone', 'Address', 'Time', 'Eviction Lawsuit', '', 'Called Status', 'Texted Status', 'Notes', 'Handoff To', 'NYSCEF', 'Retainer', 'Signed', ''].map((h, i) => (
                <th key={h + i} style={{ ...t.th, textAlign: h === '' ? 'right' : 'left', whiteSpace: 'nowrap', borderRight: i === 5 ? `1px solid ${t.textMuted}` : 'none' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map(lead => {
              const isActiveLeft = activeLeadIdLeft === lead.id;
              const isActiveRight = activeLeadIdRight === lead.id;

              let rowBg = 'transparent';
              if (isActiveLeft) rowBg = t.accentBg || 'rgba(59, 130, 246, 0.1)';
              else if (isActiveRight) rowBg = 'rgba(34, 197, 94, 0.1)'; // Soft Green

              return (
                <tr
                  key={lead.id}
                  data-testid={`lead-row-${lead.id}`}
                  style={{
                    borderBottom: `1px solid ${t.border}`,
                    backgroundColor: rowBg,
                    transition: 'background-color 0.3s ease',
                    boxShadow: isActiveLeft ? `inset 4px 0 0 ${t.accent}` : isActiveRight ? `inset 4px 0 0 #22c55e` : 'none'
                  }}
                >
                  <td style={{ ...t.td, textAlign: 'left' }}>
                    <button
                      onClick={() => onSelectLeadLeft(lead)}
                      style={{marginRight:'8px', color: t.accent, background: 'none', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: 6, borderRadius: '50%' }}
                      title="View details"
                      data-testid={`view-lead-${lead.id}`}
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    </button>
                  </td>
                  <td style={{ ...t.td, fontWeight: 500 }}>{lead.full_name || '—'}</td>
                  <td style={{ ...t.td, color: t.textMuted }}>{lead.phone_number || '—'}</td>
                  <td style={{ ...t.td, color: t.textMuted }}>{lead.street_address || '—'}</td>
                  <td style={{ ...t.td, color: t.textMuted }}>{lead.time || '—'}</td>
                  <td style={{ ...t.td, borderRight: `1px solid ${t.textMuted}` }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                      background: lead.has_eviction_lawsuit ? t.greenBg : t.accentBg,
                      color: lead.has_eviction_lawsuit ? t.green : t.accent
                    }}>
                      {lead.has_eviction_lawsuit ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td style={{ ...t.td, textAlign: 'right' }}>
                    <button
                      onClick={() => onSelectLeadRight(lead)}
                      style={{marginRight:'8px', color: t.green, background: 'none', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: 6, borderRadius: '50%' }}
                      title="View Status & Tracking"
                      data-testid={`status-lead-${lead.id}`}
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                        <polyline points="10 9 9 9 8 9"></polyline>
                      </svg>
                    </button>
                  </td>
                  <td style={{ ...t.td }}>
                    {lead.called_status ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: t.bgPage, border: `1px solid ${t.border}`, padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600, textTransform: 'capitalize', color: t.text, whiteSpace: 'nowrap' }}>
                        <div style={{ width: 6, height: 6, background: getCalledStatusColor(lead.called_status, t).color, borderRadius: '50%' }} /> {lead.called_status.toLowerCase()}
                      </span>
                    ) : <span style={{ color: t.textMuted }}>—</span>}
                  </td>
                  <td style={{ ...t.td }}>
                    {lead.texted_status ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: t.bgPage, border: `1px solid ${t.border}`, padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600, textTransform: 'capitalize', color: t.text, whiteSpace: 'nowrap' }}>
                        <div style={{ width: 6, height: 6, background: getTextedStatusColor(lead.texted_status, t).color, borderRadius: '50%' }} /> {lead.texted_status.toLowerCase()}
                      </span>
                    ) : <span style={{ color: t.textMuted }}>—</span>}
                  </td>
                  <td style={{ ...t.td, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: t.textMuted, fontSize: 13 }}>
                    {lead.followed_up_notes || '—'}
                  </td>
                  <td style={{ ...t.td }}>
                    {lead.handoff_to ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: t.bgPage, border: `1px solid ${t.border}`, padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600, textTransform: 'capitalize' }}>
                        <div style={{ width: 6, height: 6, background: t.green, borderRadius: '50%' }} /> {lead.handoff_to.toLowerCase()}
                      </span>
                    ) : <span style={{ color: t.textMuted }}>—</span>}
                  </td>
                  <td style={{ ...t.td, maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {lead.nyscef_link ? (
                      <a href={lead.nyscef_link} target="_blank" rel="noreferrer" style={{ color: t.accent, textDecoration: 'none', fontSize: 13 }}>Link</a>
                    ) : <span style={{ color: t.textMuted }}>—</span>}
                  </td>
                  <td style={{ ...t.td, fontWeight: 600, color: lead.retainer_amount ? t.green : t.textMuted }}>
                    {lead.retainer_amount ? `$${lead.retainer_amount}` : '—'}
                  </td>
                  <td style={{ ...t.td }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                      background: lead.signed ? t.greenBg : t.accentBg,
                      color: lead.signed ? t.green : t.accent
                    }}>
                      {lead.signed ? 'Signed' : 'Pending'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
