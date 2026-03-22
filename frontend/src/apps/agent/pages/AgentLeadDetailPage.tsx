/**
 * Agent Lead Detail — premium command center for a single lead.
 */

import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import {
  useAgentLead, useUpdateLeadStatus, useAddLeadNote, useLeadPipeline,
} from '../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../api/agentApi';

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function getInitials(name: string): string {
  const parts = name.trim().split(' ');
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function avatarGradient(name: string): string {
  const gradients = [
    'linear-gradient(135deg, #6366f1, #8b5cf6)',
    'linear-gradient(135deg, #0ea5e9, #6366f1)',
    'linear-gradient(135deg, #10b981, #0ea5e9)',
    'linear-gradient(135deg, #f59e0b, #ef4444)',
    'linear-gradient(135deg, #8b5cf6, #ec4899)',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return gradients[Math.abs(hash) % gradients.length];
}

function bucketConfig(bucket: string | undefined) {
  if (bucket === 'HOT') return { label: 'HOT 🔥', color: '#f87171', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)' };
  if (bucket === 'WARM') return { label: 'WARM', color: '#fb923c', bg: 'rgba(251,146,60,0.12)', border: 'rgba(251,146,60,0.3)' };
  if (bucket === 'NURTURE') return { label: 'NURTURE', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.2)' };
  return null;
}

function eventIcon(eventType: string): string {
  const t = eventType.toUpperCase();
  if (t.includes('EMAIL')) return '✉';
  if (t.includes('FORM')) return '📋';
  if (t.includes('SCORE') || t.includes('BUCKET')) return '⭐';
  if (t.includes('STAGE')) return '→';
  if (t.includes('NOTE')) return '📝';
  if (t.includes('CREATED')) return '✦';
  return '◎';
}

function eventColor(eventType: string, t: ReturnType<typeof getTokens>): string {
  const ev = eventType.toUpperCase();
  if (ev.includes('HOT') || ev.includes('SCORE')) return t.orange;
  if (ev.includes('FORM') || ev.includes('SUBMIT')) return t.green;
  if (ev.includes('EMAIL')) return t.accent;
  if (ev.includes('CREATED')) return '#8b5cf6';
  return t.textMuted;
}

const VALID_TRANSITIONS: Record<string, string[]> = {
  NEW:             ['CONTACTED'],
  INVITE_SENT:     ['CONTACTED'],
  FORM_SUBMITTED:  ['CONTACTED'],
  SCORED:          ['CONTACTED'],
  CONTACTED:       ['APPOINTMENT_SET', 'LOST'],
  APPOINTMENT_SET: ['CLOSED', 'LOST'],
  LOST:            ['CONTACTED'],
  CLOSED:          [],
};

// ── Sub-components ───────────────────────────────────────────────────────────

const SectionCard: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{
      background: t.bgCard, border: `1px solid ${t.border}`,
      borderRadius: 16, padding: '20px 22px', marginBottom: 14, ...style,
    }}>
      {children}
    </div>
  );
};

const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 14 }}>
      {children}
    </div>
  );
};

const ActionButton: React.FC<{
  icon: string; label: string; href?: string;
  disabled?: boolean; comingSoon?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost';
  onClick?: () => void;
}> = ({ icon, label, href, disabled, comingSoon, variant = 'secondary', onClick }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hovered, setHovered] = useState(false);

  const isDisabled = disabled || comingSoon;

  const styles: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 7,
    padding: '10px 16px', borderRadius: 10, fontSize: 13, fontWeight: 600,
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.15s', textDecoration: 'none', border: 'none',
    opacity: isDisabled ? 0.45 : 1,
    ...(variant === 'primary' ? {
      background: hovered && !isDisabled ? 'linear-gradient(135deg, #5558e8, #7c4fe0)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      color: '#fff', boxShadow: isDisabled ? 'none' : '0 2px 10px rgba(99,102,241,0.3)',
    } : variant === 'secondary' ? {
      background: hovered && !isDisabled ? t.bgCardHover : t.bgCard,
      color: t.text, border: `1px solid ${t.border}`,
    } : {
      background: 'transparent', color: t.textMuted,
      border: `1px solid ${hovered && !isDisabled ? t.border : 'transparent'}`,
    }),
  };

  const content = (
    <>
      <span style={{ fontSize: 15 }}>{icon}</span>
      <span>{label}</span>
      {comingSoon && (
        <span style={{ fontSize: 9, fontWeight: 700, color: t.textFaint, letterSpacing: '0.4px', marginLeft: 2 }}>
          SOON
        </span>
      )}
    </>
  );

  if (href && !isDisabled) {
    return (
      <a href={href} style={styles} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
        {content}
      </a>
    );
  }

  return (
    <button
      disabled={isDisabled}
      onClick={onClick}
      title={comingSoon ? 'Coming soon' : undefined}
      style={styles}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {content}
    </button>
  );
};

// ── Timeline Tab ─────────────────────────────────────────────────────────────

const TimelineTab: React.FC<{ detail: NonNullable<ReturnType<typeof useAgentLead>['data']> }> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  const events = [...(detail.timeline || [])].reverse();

  if (!events.length) {
    return (
      <SectionCard>
        <div style={{ textAlign: 'center', padding: '30px 0', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>◎</div>
          No activity recorded yet
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard>
      <SectionTitle>Activity Timeline</SectionTitle>
      <div style={{ position: 'relative' }}>
        {events.map((event, i) => {
          const color = eventColor(event.event_type, t);
          const icon = eventIcon(event.event_type);
          const isLast = i === events.length - 1;
          return (
            <div key={event.id} style={{ display: 'flex', gap: 14, position: 'relative' }}>
              {/* Line + dot */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 28 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: `${color}18`, border: `1.5px solid ${color}50`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, color, zIndex: 1,
                }}>
                  {icon}
                </div>
                {!isLast && (
                  <div style={{ width: 1, flex: 1, minHeight: 16, background: t.border, margin: '3px 0' }} />
                )}
              </div>
              {/* Content */}
              <div style={{ flex: 1, paddingBottom: isLast ? 0 : 16 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
                    {event.event_type.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 11, color: t.textFaint, flexShrink: 0 }}>{timeAgo(event.created_at)}</span>
                </div>
                {event.payload && Object.keys(event.payload).length > 0 && (
                  <div style={{ fontSize: 12, color: t.textMuted, marginTop: 3 }}>
                    {Object.entries(event.payload).slice(0, 2).map(([k, v]) => (
                      <span key={k} style={{ marginRight: 10 }}>{k}: <span style={{ color: t.textSecondary }}>{String(v)}</span></span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
};

// ── Pipeline Tab ──────────────────────────────────────────────────────────────

const PipelineTab: React.FC<{ pipeline: NonNullable<ReturnType<typeof useLeadPipeline>['data']> }> = ({ pipeline }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  const sortedStages = [...pipeline.stages].sort((a, b) => a.position - b.position);
  const currentIdx = sortedStages.findIndex(s => s.id === pipeline.current_stage?.id);

  return (
    <>
      {/* Current stage hero */}
      <SectionCard>
        <SectionTitle>{pipeline.pipeline_name}</SectionTitle>
        {pipeline.current_stage ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12, flexShrink: 0,
              background: `${pipeline.current_stage.color}20`,
              border: `2px solid ${pipeline.current_stage.color}60`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18,
            }}>
              →
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: t.text }}>{pipeline.current_stage.name}</div>
              <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>
                {pipeline.current_stage.category.replace(/_/g, ' ')}
                {pipeline.stage_entered_at && ` · entered ${timeAgo(pipeline.stage_entered_at)}`}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: t.textMuted }}>Not yet assigned to a stage.</div>
        )}
      </SectionCard>

      {/* Stage progress track */}
      {sortedStages.length > 0 && (
        <SectionCard>
          <SectionTitle>Pipeline Progress</SectionTitle>
          <div style={{ overflowX: 'auto', paddingBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0, minWidth: sortedStages.length * 80 }}>
              {sortedStages.map((stage, idx) => {
                const isCurrent = stage.id === pipeline.current_stage?.id;
                const isPast = idx < currentIdx;
                const isWon = stage.is_closed_won;
                const isLost = stage.is_closed_lost;
                const dotColor = isCurrent ? stage.color : isPast ? t.green : t.border;
                return (
                  <React.Fragment key={stage.id}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flexShrink: 0, minWidth: 72 }}>
                      <div style={{
                        width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                        background: dotColor,
                        border: isCurrent ? `3px solid ${stage.color}` : 'none',
                        boxShadow: isCurrent ? `0 0 10px ${stage.color}60` : 'none',
                        outline: isCurrent ? `3px solid ${stage.color}25` : 'none',
                        transition: 'all 0.2s',
                      }} />
                      <div style={{
                        fontSize: 10, textAlign: 'center', maxWidth: 68,
                        color: isCurrent ? t.text : isPast ? t.textMuted : t.textFaint,
                        fontWeight: isCurrent ? 700 : 400,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {isWon ? '✓ ' : isLost ? '✗ ' : ''}{stage.name}
                      </div>
                    </div>
                    {idx < sortedStages.length - 1 && (
                      <div style={{
                        flex: 1, height: 2, marginTop: 8, minWidth: 12,
                        background: isPast ? t.green : t.border,
                        transition: 'background 0.2s',
                      }} />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        </SectionCard>
      )}

      {/* Stage history */}
      {pipeline.stage_history.length > 0 && (
        <SectionCard>
          <SectionTitle>Stage History</SectionTitle>
          {[...pipeline.stage_history].reverse().map((h, i) => {
            const toStage = sortedStages.find(s => s.id === h.to_stage_id);
            return (
              <div key={h.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0', borderBottom: i < pipeline.stage_history.length - 1 ? `1px solid ${t.border}` : 'none',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {toStage && <div style={{ width: 8, height: 8, borderRadius: '50%', background: toStage.color, flexShrink: 0 }} />}
                  <span style={{ fontSize: 13, color: t.text }}>{toStage?.name || `Stage ${h.to_stage_id}`}</span>
                  <span style={{ fontSize: 11, color: t.textFaint, background: t.bgBadge, padding: '2px 6px', borderRadius: 5 }}>
                    {h.change_source}
                  </span>
                </div>
                <span style={{ fontSize: 11, color: t.textFaint }}>{timeAgo(h.created_at)}</span>
              </div>
            );
          })}
        </SectionCard>
      )}
    </>
  );
};

// ── Scoring Tab ───────────────────────────────────────────────────────────────

const ScoringTab: React.FC<{ detail: NonNullable<ReturnType<typeof useAgentLead>['data']> }> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const lead = detail.lead;
  const bc = bucketConfig(lead.score_bucket);
  const breakdown = detail.scoring_breakdown;

  if (!breakdown?.factors?.length) {
    return (
      <SectionCard>
        <SectionTitle>Qualification Score</SectionTitle>
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>📋</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 6 }}>
            {lead.score != null ? `Score: ${lead.score}` : 'Not yet scored'}
          </div>
          <div style={{ fontSize: 13, color: t.textMuted }}>
            {lead.score != null
              ? 'Detailed breakdown not available for this lead.'
              : 'The lead needs to submit the qualification form to receive a score.'}
          </div>
        </div>
      </SectionCard>
    );
  }

  const maxScore = breakdown.factors.reduce((sum, f) => sum + f.points, 0);
  const pct = maxScore > 0 ? Math.round((breakdown.total / maxScore) * 100) : 0;

  return (
    <SectionCard>
      <SectionTitle>Qualification Score</SectionTitle>

      {/* Score hero */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 20, padding: '16px 20px', borderRadius: 12, background: bc ? bc.bg : t.bgBadge, border: `1px solid ${bc ? bc.border : t.border}` }}>
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: bc?.color || t.text, lineHeight: 1 }}>{breakdown.total}</div>
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>/ {maxScore} pts</div>
        </div>
        <div style={{ flex: 1 }}>
          {bc && (
            <div style={{ fontSize: 14, fontWeight: 700, color: bc.color, marginBottom: 6 }}>{bc.label}</div>
          )}
          <div style={{ height: 6, borderRadius: 3, background: t.border, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 3, transition: 'width 0.5s ease',
              width: `${pct}%`,
              background: bc?.color || t.accent,
            }} />
          </div>
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 4 }}>{pct}% of max score</div>
        </div>
      </div>

      {/* Factor breakdown */}
      {breakdown.factors.map((factor, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '11px 0', borderBottom: i < breakdown.factors.length - 1 ? `1px solid ${t.border}` : 'none',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
              background: factor.met ? t.greenBg : t.bgBadge,
              border: `1.5px solid ${factor.met ? t.green : t.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, color: factor.met ? t.green : t.textFaint,
            }}>
              {factor.met ? '✓' : '○'}
            </div>
            <span style={{ fontSize: 13, color: factor.met ? t.text : t.textMuted }}>{factor.label}</span>
          </div>
          <span style={{
            fontSize: 13, fontWeight: 700,
            color: factor.met ? t.green : t.textFaint,
            background: factor.met ? t.greenBg : 'transparent',
            padding: '3px 10px', borderRadius: 6,
          }}>
            {factor.met ? `+${factor.points}` : '—'}
          </span>
        </div>
      ))}
    </SectionCard>
  );
};

// ── Emails Tab ────────────────────────────────────────────────────────────────

const EmailsTab: React.FC<{ detail: NonNullable<ReturnType<typeof useAgentLead>['data']> }> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [expanded, setExpanded] = useState<number | null>(0);

  if (!detail.rendered_emails?.length) {
    return (
      <SectionCard>
        <div style={{ textAlign: 'center', padding: '30px 0', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>✉</div>
          No emails generated yet
        </div>
      </SectionCard>
    );
  }

  return (
    <>
      {detail.rendered_emails.map((email, i) => (
        <SectionCard key={i} style={{ padding: 0, overflow: 'hidden' }}>
          <button
            onClick={() => setExpanded(expanded === i ? null : i)}
            style={{
              width: '100%', padding: '16px 20px', background: 'none', border: 'none',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
              <span style={{ fontSize: 16 }}>✉</span>
              <div style={{ minWidth: 0, textAlign: 'left' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {email.subject}
                </div>
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>
                  {email.type.replace(/_/g, ' ')}
                  {email.sent_at && ` · sent ${timeAgo(email.sent_at)}`}
                </div>
              </div>
            </div>
            <span style={{ color: t.textFaint, fontSize: 12, flexShrink: 0 }}>{expanded === i ? '▲' : '▼'}</span>
          </button>
          {expanded === i && (
            <div style={{ padding: '0 20px 18px', borderTop: `1px solid ${t.border}` }}>
              <div style={{ paddingTop: 14, fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {email.body}
              </div>
            </div>
          )}
        </SectionCard>
      ))}
    </>
  );
};

// ── Notes Tab ─────────────────────────────────────────────────────────────────

const NotesTab: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
  leadId: number;
}> = ({ detail, leadId }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const addNote = useAddLeadNote();
  const [noteText, setNoteText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setLoading(true);
    try {
      await addNote.mutateAsync({ id: leadId, content: noteText });
      setNoteText('');
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <SectionCard>
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 10 }}>
          <textarea
            value={noteText}
            onChange={e => setNoteText(e.target.value)}
            placeholder="Add a note about this lead…"
            rows={2}
            style={{
              flex: 1, padding: '10px 14px', background: t.bgInput,
              border: `1.5px solid ${t.border}`, borderRadius: 10,
              fontSize: 13, color: t.text, outline: 'none', resize: 'vertical',
              fontFamily: 'inherit', lineHeight: 1.5,
            }}
            onFocus={e => (e.target.style.borderColor = t.borderFocus)}
            onBlur={e => (e.target.style.borderColor = t.border)}
          />
          <button type="submit" disabled={loading || !noteText.trim()} style={{
            padding: '10px 18px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
            cursor: loading || !noteText.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !noteText.trim() ? 0.6 : 1, alignSelf: 'flex-start',
          }}>
            {loading ? '…' : 'Add'}
          </button>
        </form>
      </SectionCard>

      {!detail.notes?.length ? (
        <SectionCard>
          <div style={{ textAlign: 'center', padding: '20px 0', color: t.textMuted, fontSize: 13 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>📝</div>
            No notes yet
          </div>
        </SectionCard>
      ) : (
        [...detail.notes].reverse().map((note, i) => (
          <SectionCard key={i}>
            <div style={{ fontSize: 13, color: t.text, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{note.text}</div>
            <div style={{ fontSize: 11, color: t.textFaint, marginTop: 10 }}>{timeAgo(note.created_at)}</div>
          </SectionCard>
        ))
      )}
    </>
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

  const [activeTab, setActiveTab] = useState<'timeline' | 'pipeline' | 'scoring' | 'emails' | 'notes'>('timeline');
  const [statusError, setStatusError] = useState('');
  const [copied, setCopied] = useState(false);

  if (isLoading) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: t.textMuted, fontSize: 14 }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>⟳</div>
        Loading lead…
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
  const bc = bucketConfig(lead.score_bucket);
  const currentState = lead.current_state || 'NEW';
  const nextStates = VALID_TRANSITIONS[currentState] || [];
  const stageName = pipeline?.current_stage?.name || currentState.replace(/_/g, ' ');

  const handleStatusChange = async (newStatus: string) => {
    setStatusError('');
    try {
      await updateStatus.mutateAsync({ id: lead.id, status: newStatus });
    } catch (err) {
      setStatusError(getAgentErrorMessage(err));
    }
  };

  const handleCopyPhone = () => {
    if (lead.phone) {
      navigator.clipboard.writeText(lead.phone).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  const TABS = [
    { key: 'timeline', label: 'Timeline', icon: '◎' },
    { key: 'pipeline', label: 'Pipeline', icon: '→' },
    { key: 'scoring', label: 'Scoring', icon: '⭐' },
    { key: 'emails', label: 'Emails', icon: '✉' },
    { key: 'notes', label: 'Notes', icon: '📝' },
  ] as const;

  return (
    <div style={{ maxWidth: 960 }}>
      {/* Back nav */}
      <button onClick={() => navigate('/agent/leads')} style={{
        background: 'none', border: 'none', color: t.textMuted, cursor: 'pointer',
        fontSize: 13, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 6,
        padding: 0,
      }}>
        ← Back to Leads
      </button>

      {/* ── Hero card ── */}
      <div style={{
        background: t.bgCard, border: `1px solid ${lead.is_aging ? 'rgba(239,68,68,0.3)' : t.border}`,
        borderRadius: 18, padding: '24px 26px', marginBottom: 14,
        boxShadow: lead.is_aging ? '0 0 0 1px rgba(239,68,68,0.1)' : 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18, flexWrap: 'wrap' }}>
          {/* Avatar */}
          <div style={{
            width: 60, height: 60, borderRadius: '50%', flexShrink: 0,
            background: avatarGradient(lead.name || '?'),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 20, color: '#fff', fontWeight: 700, letterSpacing: '-0.5px',
            boxShadow: bc ? `0 0 0 3px ${bc.border}` : 'none',
          }}>
            {getInitials(lead.name || '?')}
          </div>

          {/* Identity */}
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
              <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: t.text, letterSpacing: '-0.5px' }}>
                {lead.name}
              </h1>
              {lead.is_aging && (
                <span style={{ fontSize: 11, color: '#f87171', fontWeight: 700, background: 'rgba(239,68,68,0.1)', padding: '3px 8px', borderRadius: 6 }}>
                  ⚠ AGING
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: t.textMuted }}>
              {lead.phone && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  📞 <span style={{ fontFamily: 'monospace', letterSpacing: '0.3px' }}>{lead.phone}</span>
                </span>
              )}
              {lead.source && <span>◎ {lead.source}</span>}
              <span>Created {timeAgo(lead.created_at)}</span>
              {lead.last_agent_action_at && <span>Last action {timeAgo(lead.last_agent_action_at)}</span>}
            </div>
          </div>

          {/* Badges */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {bc && (
              <span style={{
                fontSize: 12, fontWeight: 700, padding: '5px 12px', borderRadius: 8,
                color: bc.color, background: bc.bg, border: `1px solid ${bc.border}`,
                letterSpacing: '0.3px',
              }}>
                {bc.label}
              </span>
            )}
            {lead.score != null && (
              <span style={{ fontSize: 13, fontWeight: 700, color: t.text, background: t.bgBadge, padding: '5px 12px', borderRadius: 8, border: `1px solid ${t.border}` }}>
                {lead.score} pts
              </span>
            )}
            <span style={{
              fontSize: 12, color: t.textMuted, background: t.bgBadge,
              padding: '5px 12px', borderRadius: 8, border: `1px solid ${t.border}`,
            }}>
              {stageName}
            </span>
          </div>
        </div>
      </div>

      {/* ── Action bar ── */}
      <div style={{
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 14, padding: '14px 18px', marginBottom: 14,
        display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center',
      }}>
        {lead.phone && (
          <ActionButton icon="📞" label="Call" href={`tel:${lead.phone}`} variant="secondary" />
        )}
        {lead.phone && (
          <ActionButton
            icon={copied ? '✓' : '⎘'}
            label={copied ? 'Copied!' : 'Copy Phone'}
            variant="ghost"
            onClick={handleCopyPhone}
          />
        )}
        <ActionButton icon="✉" label="Email" href={lead.phone ? undefined : undefined} variant="secondary" disabled={!lead.phone && true} />
        <ActionButton icon="💬" label="Text Message" comingSoon variant="ghost" />

        {/* Stage transitions */}
        {nextStates.length > 0 && (
          <>
            <div style={{ width: 1, height: 28, background: t.border, margin: '0 4px' }} />
            <span style={{ fontSize: 12, color: t.textFaint }}>Move to:</span>
            {nextStates.map(s => (
              <button key={s} onClick={() => handleStatusChange(s)} disabled={updateStatus.isPending} style={{
                padding: '8px 14px', borderRadius: 9, fontSize: 12, fontWeight: 600, cursor: 'pointer',
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

      {/* ── Two-column layout ── */}
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 14, background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 12, padding: 4 }}>
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  flex: 1, padding: '8px 10px', borderRadius: 9, fontSize: 12, fontWeight: 500,
                  cursor: 'pointer', transition: 'all 0.15s', border: 'none',
                  background: activeTab === tab.key ? t.accentBg : 'transparent',
                  color: activeTab === tab.key ? t.accent : t.textMuted,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                }}
              >
                <span style={{ fontSize: 13 }}>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {activeTab === 'timeline' && <TimelineTab detail={detail} />}
          {activeTab === 'pipeline' && (
            pipeline
              ? <PipelineTab pipeline={pipeline} />
              : <SectionCard><div style={{ fontSize: 13, color: t.textMuted, textAlign: 'center', padding: '20px 0' }}>No pipeline assigned to this lead.</div></SectionCard>
          )}
          {activeTab === 'scoring' && <ScoringTab detail={detail} />}
          {activeTab === 'emails' && <EmailsTab detail={detail} />}
          {activeTab === 'notes' && <NotesTab detail={detail} leadId={lead.id} />}
        </div>

        {/* Right sidebar */}
        <div style={{ width: 240, flexShrink: 0 }}>
          {/* Lead summary */}
          <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 12 }}>
              Lead Summary
            </div>
            {[
              { label: 'Status', value: currentState.replace(/_/g, ' ') },
              { label: 'Stage', value: stageName },
              { label: 'Score', value: lead.score != null ? `${lead.score} pts` : '—' },
              { label: 'Bucket', value: lead.score_bucket || '—' },
              { label: 'Source', value: lead.source || '—' },
            ].map(row => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${t.border}` }}>
                <span style={{ fontSize: 12, color: t.textFaint }}>{row.label}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: t.text }}>{row.value}</span>
              </div>
            ))}
          </div>

          {/* Qualification summary */}
          <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 12 }}>
              Qualification
            </div>
            {detail.scoring_breakdown?.factors?.length ? (
              detail.scoring_breakdown.factors.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '5px 0' }}>
                  <span style={{ fontSize: 11, color: f.met ? t.green : t.textFaint }}>{f.met ? '✓' : '○'}</span>
                  <span style={{ fontSize: 11, color: f.met ? t.text : t.textFaint, flex: 1 }}>{f.label}</span>
                </div>
              ))
            ) : (
              <div style={{ fontSize: 12, color: t.textFaint }}>No form submitted yet</div>
            )}
          </div>

          {/* Communication placeholder */}
          <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 12 }}>
              Communications
            </div>
            <div style={{ fontSize: 12, color: t.textFaint, lineHeight: 1.6 }}>
              {detail.rendered_emails?.length
                ? `${detail.rendered_emails.length} email${detail.rendered_emails.length !== 1 ? 's' : ''} sent`
                : 'No emails sent yet'}
            </div>
            <div style={{ marginTop: 10, padding: '8px 10px', borderRadius: 8, background: t.bgBadge, border: `1px dashed ${t.border}` }}>
              <div style={{ fontSize: 11, color: t.textFaint }}>SMS & call log</div>
              <div style={{ fontSize: 10, color: t.textFaint, marginTop: 2 }}>Coming soon</div>
            </div>
          </div>

          {/* Documents placeholder */}
          <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 12 }}>
              Documents
            </div>
            <div style={{ padding: '10px', borderRadius: 8, background: t.bgBadge, border: `1px dashed ${t.border}`, textAlign: 'center' }}>
              <div style={{ fontSize: 20, marginBottom: 6 }}>📄</div>
              <div style={{ fontSize: 11, color: t.textFaint }}>Document uploads</div>
              <div style={{ fontSize: 10, color: t.textFaint, marginTop: 2 }}>Coming soon</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
