/**
 * Agent Lead Detail — premium lead command center.
 * Single continuous view, no tabs. Mobile-first, two-column on desktop.
 * Order: hero → actions → pipeline → timeline → scoring → emails → notes → pending cards
 */

import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import {
  useAgentLead, useUpdateLeadStatus, useAddLeadNote, useLeadPipeline,
} from '../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../api/agentApi';
import { BackendPendingBadge } from '../components/BackendPendingBadge';

// ── Responsive CSS ────────────────────────────────────────────────────────────

if (typeof document !== 'undefined' && !document.getElementById('agent-detail-css')) {
  const s = document.createElement('style');
  s.id = 'agent-detail-css';
  s.textContent = `
    .ld-layout { display: flex; gap: 16px; align-items: flex-start; }
    .ld-main   { flex: 1; min-width: 0; }
    .ld-aside  { width: 248px; flex-shrink: 0; }
    .ld-action-bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    @media (max-width: 767px) {
      .ld-layout { flex-direction: column; }
      .ld-aside  { width: 100%; }
      .ld-action-bar { gap: 6px; }
    }
  `;
  document.head.appendChild(s);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function initials(name: string): string {
  const p = name.trim().split(' ');
  return p.length >= 2 ? (p[0][0] + p[p.length - 1][0]).toUpperCase() : name.slice(0, 2).toUpperCase();
}

function avatarGrad(name: string): string {
  const g = [
    'linear-gradient(135deg,#6366f1,#8b5cf6)',
    'linear-gradient(135deg,#0ea5e9,#6366f1)',
    'linear-gradient(135deg,#10b981,#0ea5e9)',
    'linear-gradient(135deg,#f59e0b,#ef4444)',
    'linear-gradient(135deg,#8b5cf6,#ec4899)',
  ];
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return g[Math.abs(h) % g.length];
}

function bucketCfg(b?: string) {
  if (b === 'HOT')    return { label: 'HOT 🔥', color: '#f87171', bg: 'rgba(239,68,68,0.12)',    border: 'rgba(239,68,68,0.3)' };
  if (b === 'WARM')   return { label: 'WARM',   color: '#fb923c', bg: 'rgba(251,146,60,0.12)',   border: 'rgba(251,146,60,0.3)' };
  if (b === 'NURTURE')return { label: 'NURTURE',color: '#94a3b8', bg: 'rgba(148,163,184,0.1)',   border: 'rgba(148,163,184,0.2)' };
  return null;
}

function evIcon(t: string): string {
  const u = t.toUpperCase();
  if (u.includes('EMAIL'))  return '✉';
  if (u.includes('FORM'))   return '📋';
  if (u.includes('SCORE') || u.includes('BUCKET')) return '⭐';
  if (u.includes('STAGE'))  return '→';
  if (u.includes('NOTE'))   return '📝';
  if (u.includes('CREATED'))return '✦';
  return '◎';
}

function evColor(type: string, t: ReturnType<typeof getTokens>): string {
  const u = type.toUpperCase();
  if (u.includes('HOT') || u.includes('SCORE')) return t.orange;
  if (u.includes('FORM') || u.includes('SUBMIT')) return t.green;
  if (u.includes('EMAIL')) return t.accent;
  if (u.includes('CREATED')) return '#8b5cf6';
  return t.textMuted;
}

const TRANSITIONS: Record<string, string[]> = {
  NEW: ['CONTACTED'], INVITE_SENT: ['CONTACTED'],
  FORM_SUBMITTED: ['CONTACTED'], SCORED: ['CONTACTED'],
  CONTACTED: ['APPOINTMENT_SET', 'LOST'],
  APPOINTMENT_SET: ['CLOSED', 'LOST'],
  LOST: ['CONTACTED'], CLOSED: [],
};

// ── Shared primitives ─────────────────────────────────────────────────────────

const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '18px 20px', marginBottom: 12, ...style }}>
      {children}
    </div>
  );
};

const CardTitle: React.FC<{ children: React.ReactNode; aside?: React.ReactNode }> = ({ children, aside }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px' }}>
        {children}
      </div>
      {aside}
    </div>
  );
};

const Divider: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return <div style={{ height: 1, background: t.border, margin: '10px 0' }} />;
};

// ── Action button ─────────────────────────────────────────────────────────────

const Btn: React.FC<{
  icon: string; label: string; href?: string;
  disabled?: boolean; pending?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  onClick?: () => void; title?: string;
}> = ({ icon, label, href, disabled, pending, variant = 'secondary', onClick, title }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  const off = disabled || pending;

  const base: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '9px 14px', borderRadius: 10, fontSize: 13, fontWeight: 600,
    cursor: off ? 'not-allowed' : 'pointer', transition: 'all 0.15s',
    textDecoration: 'none', border: 'none', opacity: off ? 0.45 : 1, flexShrink: 0,
    ...(variant === 'primary' ? {
      background: hov && !off ? 'linear-gradient(135deg,#5558e8,#7c4fe0)' : 'linear-gradient(135deg,#6366f1,#8b5cf6)',
      color: '#fff', boxShadow: off ? 'none' : '0 2px 10px rgba(99,102,241,0.3)',
    } : variant === 'danger' ? {
      background: hov && !off ? t.redBg : 'transparent',
      color: t.red, border: `1px solid ${hov && !off ? t.red + '60' : t.border}`,
    } : variant === 'ghost' ? {
      background: 'transparent', color: t.textMuted,
      border: `1px solid ${hov && !off ? t.border : 'transparent'}`,
    } : {
      background: hov && !off ? t.bgCardHover : t.bgCard,
      color: t.text, border: `1px solid ${t.border}`,
    }),
  };

  const inner = (
    <>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span>{label}</span>
      {pending && <BackendPendingBadge variant="inline" tooltip="Not yet supported by backend" />}
    </>
  );

  if (href && !off) return <a href={href} style={base} title={title} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}>{inner}</a>;
  return (
    <button disabled={off} onClick={onClick} title={title || (pending ? 'Not yet supported' : undefined)} style={base}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}>
      {inner}
    </button>
  );
};

// ── Section: Pipeline ─────────────────────────────────────────────────────────

const PipelineSection: React.FC<{
  pipeline: NonNullable<ReturnType<typeof useLeadPipeline>['data']>;
}> = ({ pipeline }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const sorted = [...pipeline.stages].sort((a, b) => a.position - b.position);
  const curIdx = sorted.findIndex(s => s.id === pipeline.current_stage?.id);

  return (
    <Card>
      <CardTitle>{pipeline.pipeline_name} · Pipeline</CardTitle>

      {/* Current stage hero row */}
      {pipeline.current_stage && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18,
          padding: '14px 16px', borderRadius: 12,
          background: `${pipeline.current_stage.color}12`,
          border: `1px solid ${pipeline.current_stage.color}40`,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, flexShrink: 0,
            background: `${pipeline.current_stage.color}25`,
            border: `2px solid ${pipeline.current_stage.color}70`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
          }}>→</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>{pipeline.current_stage.name}</div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
              {pipeline.current_stage.category.replace(/_/g, ' ')}
              {pipeline.stage_entered_at && ` · entered ${timeAgo(pipeline.stage_entered_at)}`}
            </div>
          </div>
        </div>
      )}

      {/* Progress track */}
      {sorted.length > 0 && (
        <div style={{ overflowX: 'auto', paddingBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', minWidth: sorted.length * 76 }}>
            {sorted.map((stage, idx) => {
              const isCur = stage.id === pipeline.current_stage?.id;
              const isPast = idx < curIdx;
              const dot = isCur ? stage.color : isPast ? t.green : t.border;
              return (
                <React.Fragment key={stage.id}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, flexShrink: 0, minWidth: 68 }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: '50%', background: dot,
                      border: isCur ? `3px solid ${stage.color}` : 'none',
                      boxShadow: isCur ? `0 0 8px ${stage.color}70` : 'none',
                      outline: isCur ? `3px solid ${stage.color}20` : 'none',
                      transition: 'all 0.2s',
                    }} />
                    <div style={{
                      fontSize: 9, textAlign: 'center', maxWidth: 64,
                      color: isCur ? t.text : isPast ? t.textMuted : t.textFaint,
                      fontWeight: isCur ? 700 : 400,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {stage.is_closed_won ? '✓ ' : stage.is_closed_lost ? '✗ ' : ''}{stage.name}
                    </div>
                  </div>
                  {idx < sorted.length - 1 && (
                    <div style={{ flex: 1, height: 2, marginTop: 7, minWidth: 8, background: isPast ? t.green : t.border, transition: 'background 0.2s' }} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* Stage history — compact */}
      {pipeline.stage_history.length > 0 && (
        <>
          <Divider />
          <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 10 }}>
            Stage History
          </div>
          {[...pipeline.stage_history].reverse().slice(0, 5).map((h, i) => {
            const st = sorted.find(s => s.id === h.to_stage_id);
            return (
              <div key={h.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < Math.min(pipeline.stage_history.length, 5) - 1 ? `1px solid ${t.border}` : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {st && <div style={{ width: 7, height: 7, borderRadius: '50%', background: st.color, flexShrink: 0 }} />}
                  <span style={{ fontSize: 12, color: t.text }}>{st?.name || `Stage ${h.to_stage_id}`}</span>
                  <span style={{ fontSize: 10, color: t.textFaint, background: t.bgBadge, padding: '1px 5px', borderRadius: 4 }}>{h.change_source}</span>
                </div>
                <span style={{ fontSize: 11, color: t.textFaint }}>{timeAgo(h.created_at)}</span>
              </div>
            );
          })}
        </>
      )}
    </Card>
  );
};

// ── Section: Timeline ─────────────────────────────────────────────────────────

const TimelineSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [showAll, setShowAll] = useState(false);
  const events = [...(detail.timeline || [])].reverse();
  const visible = showAll ? events : events.slice(0, 8);

  return (
    <Card>
      <CardTitle>Activity Timeline</CardTitle>
      {!events.length ? (
        <div style={{ textAlign: 'center', padding: '24px 0', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>◎</div>
          No activity recorded yet
        </div>
      ) : (
        <>
          {visible.map((ev, i) => {
            const color = evColor(ev.event_type, t);
            const icon = evIcon(ev.event_type);
            const isLast = i === visible.length - 1;
            return (
              <div key={ev.id} style={{ display: 'flex', gap: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 26 }}>
                  <div style={{
                    width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                    background: `${color}15`, border: `1.5px solid ${color}45`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, color, zIndex: 1,
                  }}>{icon}</div>
                  {!isLast && <div style={{ width: 1, flex: 1, minHeight: 12, background: t.border, margin: '2px 0' }} />}
                </div>
                <div style={{ flex: 1, paddingBottom: isLast ? 0 : 14 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
                      {ev.event_type.replace(/_/g, ' ')}
                    </span>
                    <span style={{ fontSize: 11, color: t.textFaint, flexShrink: 0 }}>{timeAgo(ev.created_at)}</span>
                  </div>
                  {ev.payload && Object.keys(ev.payload).length > 0 && (
                    <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
                      {Object.entries(ev.payload).slice(0, 2).map(([k, v]) => (
                        <span key={k} style={{ marginRight: 10 }}>{k}: <span style={{ color: t.textSecondary }}>{String(v)}</span></span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {events.length > 8 && (
            <button onClick={() => setShowAll(v => !v)} style={{
              marginTop: 8, background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 12, color: t.accent, padding: 0,
            }}>
              {showAll ? '▲ Show less' : `▼ Show all ${events.length} events`}
            </button>
          )}
        </>
      )}
    </Card>
  );
};

// ── Section: Scoring ──────────────────────────────────────────────────────────

const ScoringSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const lead = detail.lead;
  const bc = bucketCfg(lead.score_bucket);
  const bd = detail.scoring_breakdown;

  return (
    <Card>
      <CardTitle>Qualification Score</CardTitle>

      {bd?.factors?.length ? (() => {
        const max = bd.factors.reduce((s, f) => s + f.points, 0);
        const pct = max > 0 ? Math.round((bd.total / max) * 100) : 0;
        return (
          <>
            {/* Score hero */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 18, marginBottom: 16,
              padding: '14px 16px', borderRadius: 12,
              background: bc ? bc.bg : t.bgBadge, border: `1px solid ${bc ? bc.border : t.border}`,
            }}>
              <div style={{ textAlign: 'center', flexShrink: 0 }}>
                <div style={{ fontSize: 34, fontWeight: 800, color: bc?.color || t.text, lineHeight: 1 }}>{bd.total}</div>
                <div style={{ fontSize: 10, color: t.textFaint, marginTop: 2 }}>/ {max} pts</div>
              </div>
              <div style={{ flex: 1 }}>
                {bc && <div style={{ fontSize: 13, fontWeight: 700, color: bc.color, marginBottom: 5 }}>{bc.label}</div>}
                <div style={{ height: 5, borderRadius: 3, background: t.border, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 3, width: `${pct}%`, background: bc?.color || t.accent, transition: 'width 0.5s ease' }} />
                </div>
                <div style={{ fontSize: 10, color: t.textFaint, marginTop: 3 }}>{pct}% of max</div>
              </div>
            </div>
            {/* Factor rows */}
            {bd.factors.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '9px 0', borderBottom: i < bd.factors.length - 1 ? `1px solid ${t.border}` : 'none',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                    background: f.met ? t.greenBg : t.bgBadge,
                    border: `1.5px solid ${f.met ? t.green : t.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, color: f.met ? t.green : t.textFaint,
                  }}>{f.met ? '✓' : '○'}</div>
                  <span style={{ fontSize: 13, color: f.met ? t.text : t.textMuted }}>{f.label}</span>
                </div>
                <span style={{
                  fontSize: 12, fontWeight: 700, padding: '2px 9px', borderRadius: 6,
                  color: f.met ? t.green : t.textFaint,
                  background: f.met ? t.greenBg : 'transparent',
                }}>{f.met ? `+${f.points}` : '—'}</span>
              </div>
            ))}
          </>
        );
      })() : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 0' }}>
          <div style={{ fontSize: 28 }}>📋</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>
              {lead.score != null ? `Score: ${lead.score} pts` : 'Not yet scored'}
            </div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
              {lead.score != null ? 'Detailed breakdown unavailable.' : 'Lead must submit the qualification form.'}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};

// ── Section: Emails ───────────────────────────────────────────────────────────

const EmailsSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [expanded, setExpanded] = useState<number | null>(null);
  const emails = detail.rendered_emails || [];

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '18px 20px 14px' }}>
        <CardTitle>
          Emails Sent
          {emails.length > 0 && (
            <span style={{ fontSize: 11, color: t.textFaint, background: t.bgBadge, padding: '2px 8px', borderRadius: 5 }}>
              {emails.length}
            </span>
          )}
        </CardTitle>
      </div>
      {!emails.length ? (
        <div style={{ padding: '0 20px 20px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 22, marginBottom: 6 }}>✉</div>
          No emails sent yet
        </div>
      ) : (
        emails.map((email, i) => (
          <div key={i} style={{ borderTop: `1px solid ${t.border}` }}>
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              style={{
                width: '100%', padding: '13px 20px', background: 'none', border: 'none',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}>✉</span>
                <div style={{ minWidth: 0, textAlign: 'left' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {email.subject}
                  </div>
                  <div style={{ fontSize: 11, color: t.textFaint, marginTop: 1 }}>
                    {email.type.replace(/_/g, ' ')}
                    {email.sent_at && ` · ${timeAgo(email.sent_at)}`}
                  </div>
                </div>
              </div>
              <span style={{ color: t.textFaint, fontSize: 11, flexShrink: 0 }}>{expanded === i ? '▲' : '▼'}</span>
            </button>
            {expanded === i && (
              <div style={{ padding: '0 20px 16px', borderTop: `1px solid ${t.border}` }}>
                <div style={{ paddingTop: 12, fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                  {email.body}
                </div>
              </div>
            )}
          </div>
        ))
      )}
    </Card>
  );
};

// ── Section: Notes ────────────────────────────────────────────────────────────

const NotesSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
  leadId: number;
}> = ({ detail, leadId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const addNote = useAddLeadNote();
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try { await addNote.mutateAsync({ id: leadId, content: text }); setText(''); }
    catch { /* ignore */ } finally { setSaving(false); }
  };

  const notes = [...(detail.notes || [])].reverse();

  return (
    <Card>
      <CardTitle>Notes</CardTitle>
      <form onSubmit={submit} style={{ display: 'flex', gap: 10, marginBottom: notes.length ? 16 : 0 }}>
        <textarea
          value={text} onChange={e => setText(e.target.value)}
          placeholder="Add an internal note…" rows={2}
          style={{
            flex: 1, padding: '9px 12px', background: t.bgInput,
            border: `1.5px solid ${t.border}`, borderRadius: 10,
            fontSize: 13, color: t.text, outline: 'none', resize: 'vertical',
            fontFamily: 'inherit', lineHeight: 1.5,
          }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)}
          onBlur={e => (e.target.style.borderColor = t.border)}
        />
        <button type="submit" disabled={saving || !text.trim()} style={{
          padding: '9px 16px', background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
          border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
          cursor: saving || !text.trim() ? 'not-allowed' : 'pointer',
          opacity: saving || !text.trim() ? 0.6 : 1, alignSelf: 'flex-start',
        }}>{saving ? '…' : 'Add'}</button>
      </form>
      {notes.map((n, i) => (
        <div key={i} style={{ padding: '12px 0', borderTop: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 13, color: t.text, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{n.text}</div>
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 6 }}>{timeAgo(n.created_at)}</div>
        </div>
      ))}
      {!notes.length && (
        <div style={{ fontSize: 12, color: t.textFaint, textAlign: 'center', padding: '12px 0' }}>No notes yet</div>
      )}
    </Card>
  );
};

// ── Sidebar cards ─────────────────────────────────────────────────────────────

const SidebarSummary: React.FC<{
  lead: NonNullable<ReturnType<typeof useAgentLead>['data']>['lead'];
  stageName: string;
  currentState: string;
}> = ({ lead, stageName, currentState }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const bc = bucketCfg(lead.score_bucket);

  const rows = [
    { label: 'Status',  value: currentState.replace(/_/g, ' ') },
    { label: 'Stage',   value: stageName },
    { label: 'Score',   value: lead.score != null ? `${lead.score} pts` : '—' },
    { label: 'Bucket',  value: lead.score_bucket || '—', color: bc?.color },
    { label: 'Source',  value: lead.source || '—' },
    { label: 'Created', value: timeAgo(lead.created_at) },
  ];

  return (
    <Card>
      <CardTitle>Lead Summary</CardTitle>
      {rows.map((r, i) => (
        <div key={r.label} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '6px 0', borderBottom: i < rows.length - 1 ? `1px solid ${t.border}` : 'none',
        }}>
          <span style={{ fontSize: 12, color: t.textFaint }}>{r.label}</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: r.color || t.text }}>{r.value}</span>
        </div>
      ))}
    </Card>
  );
};

const SidebarQualification: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const factors = detail.scoring_breakdown?.factors || [];

  return (
    <Card>
      <CardTitle>Qualification</CardTitle>
      {factors.length ? (
        factors.map((f, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '4px 0' }}>
            <span style={{ fontSize: 11, color: f.met ? t.green : t.textFaint, flexShrink: 0 }}>{f.met ? '✓' : '○'}</span>
            <span style={{ fontSize: 12, color: f.met ? t.text : t.textFaint, flex: 1 }}>{f.label}</span>
            {f.met && <span style={{ fontSize: 11, color: t.green, fontWeight: 700 }}>+{f.points}</span>}
          </div>
        ))
      ) : (
        <div style={{ fontSize: 12, color: t.textFaint }}>No form submitted yet</div>
      )}
    </Card>
  );
};

const SidebarComms: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const emailCount = detail.rendered_emails?.length || 0;

  return (
    <Card>
      <CardTitle>Communications</CardTitle>
      <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 10 }}>
        {emailCount ? `${emailCount} email${emailCount !== 1 ? 's' : ''} sent` : 'No emails sent yet'}
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 10px', borderRadius: 8, background: t.bgBadge, border: `1px dashed ${t.border}`,
      }}>
        <span style={{ fontSize: 12, color: t.textFaint }}>SMS & call log</span>
        <BackendPendingBadge tooltip="SMS and call log — coming soon" />
      </div>
    </Card>
  );
};

const SidebarDocuments: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <Card>
      <CardTitle aside={<BackendPendingBadge tooltip="Document uploads — coming soon" />}>
        Documents
      </CardTitle>
      <div style={{
        padding: '14px', borderRadius: 10, background: t.bgBadge,
        border: `1px dashed ${t.border}`, textAlign: 'center',
      }}>
        <div style={{ fontSize: 22, marginBottom: 6 }}>📄</div>
        <div style={{ fontSize: 12, color: t.textFaint }}>No documents yet</div>
      </div>
    </Card>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────

export const AgentLeadDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const t = getTokens(theme);

  const { data: detail, isLoading, error } = useAgentLead(Number(id));
  const updateStatus = useUpdateLeadStatus();
  const { data: pipeline } = useLeadPipeline(Number(id));

  const [statusError, setStatusError] = useState('');
  const [copied, setCopied] = useState(false);

  if (isLoading) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: t.textMuted, fontSize: 14 }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>⟳</div>Loading lead…
      </div>
    );
  }
  if (error || !detail) {
    return (
      <div style={{ padding: 60, textAlign: 'center' }}>
        <div style={{ color: t.red, fontSize: 14, marginBottom: 12 }}>Lead not found or access denied.</div>
        <button onClick={() => navigate('/agent/leads')} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}>
          ← Back to Leads
        </button>
      </div>
    );
  }

  const lead = detail.lead;
  const bc = bucketCfg(lead.score_bucket);
  const currentState = lead.current_state || 'NEW';
  const nextStates = TRANSITIONS[currentState] || [];
  const stageName = pipeline?.current_stage?.name || currentState.replace(/_/g, ' ');

  const handleMove = async (s: string) => {
    setStatusError('');
    try { await updateStatus.mutateAsync({ id: lead.id, status: s }); }
    catch (err) { setStatusError(getAgentErrorMessage(err)); }
  };

  const copyPhone = () => {
    if (!lead.phone) return;
    navigator.clipboard.writeText(lead.phone).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div style={{ maxWidth: 980 }}>
      {/* ── Back ── */}
      <button onClick={() => navigate('/agent/leads')} style={{
        background: 'none', border: 'none', color: t.textMuted, cursor: 'pointer',
        fontSize: 13, marginBottom: 18, display: 'flex', alignItems: 'center', gap: 6, padding: 0,
      }}>
        ← Back to Leads
      </button>

      {/* ── Hero ── */}
      <div style={{
        background: t.bgCard,
        border: `1px solid ${lead.is_aging ? 'rgba(239,68,68,0.3)' : t.border}`,
        borderRadius: 18, padding: '22px 24px', marginBottom: 10,
        boxShadow: lead.is_aging ? '0 0 0 1px rgba(239,68,68,0.08)' : 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          {/* Avatar */}
          <div style={{
            width: 58, height: 58, borderRadius: '50%', flexShrink: 0,
            background: avatarGrad(lead.name || '?'),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 19, color: '#fff', fontWeight: 700, letterSpacing: '-0.5px',
            boxShadow: bc ? `0 0 0 3px ${bc.border}` : 'none',
          }}>
            {initials(lead.name || '?')}
          </div>

          {/* Identity block */}
          <div style={{ flex: 1, minWidth: 160 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 5 }}>
              <h1 style={{ margin: 0, fontSize: 21, fontWeight: 800, color: t.text, letterSpacing: '-0.5px' }}>
                {lead.name}
              </h1>
              {lead.is_aging && (
                <span style={{ fontSize: 10, color: '#f87171', fontWeight: 700, background: 'rgba(239,68,68,0.1)', padding: '3px 8px', borderRadius: 6, letterSpacing: '0.3px' }}>
                  ⚠ AGING
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 13, color: t.textMuted }}>
              {lead.phone && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  📞 <span style={{ fontFamily: 'monospace', letterSpacing: '0.3px' }}>{lead.phone}</span>
                </span>
              )}
              {lead.email && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  ✉ <span>{lead.email}</span>
                </span>
              )}
              {lead.source && <span>◎ {lead.source}</span>}
              <span style={{ color: t.textFaint }}>Created {timeAgo(lead.created_at)}</span>
              {lead.last_agent_action_at && (
                <span style={{ color: t.textFaint }}>Last action {timeAgo(lead.last_agent_action_at)}</span>
              )}
            </div>
          </div>

          {/* Badges */}
          <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', alignItems: 'center' }}>
            {bc && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '5px 11px', borderRadius: 8,
                color: bc.color, background: bc.bg, border: `1px solid ${bc.border}`, letterSpacing: '0.3px',
              }}>{bc.label}</span>
            )}
            {lead.score != null && (
              <span style={{ fontSize: 12, fontWeight: 700, color: t.text, background: t.bgBadge, padding: '5px 11px', borderRadius: 8, border: `1px solid ${t.border}` }}>
                {lead.score} pts
              </span>
            )}
            <span style={{ fontSize: 11, color: t.textMuted, background: t.bgBadge, padding: '5px 11px', borderRadius: 8, border: `1px solid ${t.border}` }}>
              {stageName}
            </span>
          </div>
        </div>
      </div>

      {/* ── Action bar ── */}
      <div style={{
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 14, padding: '11px 14px', marginBottom: 14,
      }}>
        <div className="ld-action-bar">
          {lead.phone && <Btn icon="📞" label="Call" href={`tel:${lead.phone}`} />}
          {lead.email && <Btn icon="✉" label="Email" href={`mailto:${lead.email}`} />}
          {lead.phone && (
            <Btn icon={copied ? '✓' : '⎘'} label={copied ? 'Copied!' : 'Copy Phone'} variant="ghost" onClick={copyPhone} />
          )}
          <Btn icon="💬" label="Text" pending variant="ghost" />

          {nextStates.length > 0 && (
            <>
              <div style={{ width: 1, height: 26, background: t.border, margin: '0 2px', flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: t.textFaint, flexShrink: 0 }}>Move to:</span>
              {nextStates.map(s => (
                <button key={s} onClick={() => handleMove(s)} disabled={updateStatus.isPending} style={{
                  padding: '7px 13px', borderRadius: 9, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  background: t.accentBg, border: `1px solid ${t.accent}40`, color: t.accent,
                  opacity: updateStatus.isPending ? 0.6 : 1, transition: 'all 0.15s',
                }}>
                  {s.replace(/_/g, ' ')}
                </button>
              ))}
            </>
          )}
          {statusError && <span style={{ fontSize: 12, color: t.red }}>{statusError}</span>}
        </div>
      </div>

      {/* ── Two-column body ── */}
      <div className="ld-layout">
        {/* Main column */}
        <div className="ld-main">
          {/* Pipeline */}
          {pipeline
            ? <PipelineSection pipeline={pipeline} />
            : (
              <Card>
                <CardTitle>Pipeline</CardTitle>
                <div style={{ fontSize: 13, color: t.textMuted }}>No pipeline assigned to this lead.</div>
              </Card>
            )
          }

          {/* Timeline */}
          <TimelineSection detail={detail} />

          {/* Scoring */}
          <ScoringSection detail={detail} />

          {/* Emails */}
          <EmailsSection detail={detail} />

          {/* Notes */}
          <NotesSection detail={detail} leadId={lead.id} />
        </div>

        {/* Sidebar */}
        <div className="ld-aside">
          <SidebarSummary lead={lead} stageName={stageName} currentState={currentState} />
          <SidebarQualification detail={detail} />
          <SidebarComms detail={detail} />
          <SidebarDocuments />
        </div>
      </div>
    </div>
  );
};
