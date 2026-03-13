/**
 * Agent Lead Detail — scoring breakdown, timeline, email previews, notes, status controls.
 */

import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { useAgentLead, useUpdateLeadStatus, useAddLeadNote } from '../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../api/agentApi';

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

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function bucketColor(bucket: string | undefined, t: ReturnType<typeof getTokens>) {
  if (bucket === 'HOT') return t.red;
  if (bucket === 'WARM') return t.orange;
  return t.textMuted;
}

export const AgentLeadDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const t = getTokens(theme);

  const { data: detail, isLoading, error } = useAgentLead(Number(id));
  const updateStatus = useUpdateLeadStatus();
  const addNote = useAddLeadNote();

  const [noteText, setNoteText] = useState('');
  const [noteLoading, setNoteLoading] = useState(false);
  const [statusError, setStatusError] = useState('');
  const [activeTab, setActiveTab] = useState<'scoring' | 'timeline' | 'emails' | 'notes'>('scoring');

  if (isLoading) {
    return <div style={{ padding: 40, textAlign: 'center', color: t.textMuted, fontSize: 14 }}>Loading lead…</div>;
  }
  if (error || !detail) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ color: t.red, fontSize: 14, marginBottom: 12 }}>Lead not found or access denied.</div>
        <button onClick={() => navigate('/agent/leads')} style={{ color: t.accent, background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}>← Back to Leads</button>
      </div>
    );
  }

  // Backend returns { lead: {...}, scoring_breakdown: {...}, timeline: [...], ... }
  const lead = detail.lead;
  const currentState = lead.current_state || 'NEW';
  const nextStates = VALID_TRANSITIONS[currentState] || [];

  const handleStatusChange = async (newStatus: string) => {
    setStatusError('');
    try {
      await updateStatus.mutateAsync({ id: lead.id, status: newStatus });
    } catch (err) {
      setStatusError(getAgentErrorMessage(err));
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setNoteLoading(true);
    try {
      await addNote.mutateAsync({ id: lead.id, content: noteText });
      setNoteText('');
    } catch { /* ignore */ } finally {
      setNoteLoading(false);
    }
  };

  const cardStyle = { background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '20px 22px', marginBottom: 16 };
  const tabStyle = (active: boolean) => ({
    padding: '11px 16px', minHeight: 44, borderRadius: 9, fontSize: 13, fontWeight: 500 as const, cursor: 'pointer' as const,
    background: active ? t.accentBg : 'transparent',
    border: `1px solid ${active ? t.accent : t.border}`,
    color: active ? t.accent : t.textMuted,
    transition: 'all 0.15s',
  });

  return (
    <div style={{ maxWidth: 800 }}>
      {/* Back */}
      <button onClick={() => navigate('/agent/leads')} style={{
        background: 'none', border: 'none', color: t.textMuted, cursor: 'pointer',
        fontSize: 13, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 6,
      }}>← Back to Leads</button>

      {/* Header card */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: '50%',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, color: '#fff', fontWeight: 700, flexShrink: 0,
            }}>
              {lead.name?.[0]?.toUpperCase() || '?'}
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px' }}>{lead.name}</div>
              {lead.phone && <div style={{ fontSize: 13, color: t.textMuted }}>{lead.phone}</div>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            {lead.score_bucket && (
              <span style={{
                fontSize: 13, fontWeight: 700, padding: '5px 12px', borderRadius: 10,
                color: bucketColor(lead.score_bucket, t),
                background: lead.score_bucket === 'HOT' ? t.redBg : lead.score_bucket === 'WARM' ? t.orangeBg : t.bgBadge,
              }}>
                {lead.score_bucket}
              </span>
            )}
            {lead.score != null && (
              <span style={{ fontSize: 13, color: t.textMuted, background: t.bgBadge, padding: '5px 12px', borderRadius: 10 }}>
                {lead.score} pts
              </span>
            )}
            <span style={{ fontSize: 13, color: t.textMuted, background: t.bgBadge, padding: '5px 12px', borderRadius: 10 }}>
              {currentState}
            </span>
          </div>
        </div>

        {lead.address && (
          <div style={{ marginTop: 14, fontSize: 13, color: t.textSecondary }}>
            📍 {lead.address}
            {lead.listing_url && (
              <a href={lead.listing_url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 10, color: t.accent, fontSize: 12 }}>
                View listing →
              </a>
            )}
          </div>
        )}

        <div style={{ marginTop: 12, fontSize: 12, color: t.textFaint }}>
          {lead.source && <span>Source: {lead.source} · </span>}
          Created {timeAgo(lead.created_at)}
          {lead.last_agent_action_at && <span> · Last action {timeAgo(lead.last_agent_action_at)}</span>}
          {lead.is_aging && <span style={{ color: t.red, fontWeight: 600 }}> · ⚠ AGING</span>}
        </div>
      </div>

      {/* Status controls */}
      {nextStates.length > 0 && (
        <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', rowGap: 10 }}>
          <span style={{ fontSize: 13, color: t.textMuted, fontWeight: 500 }}>Update status:</span>
          {nextStates.map(s => (
            <button key={s} onClick={() => handleStatusChange(s)} disabled={updateStatus.isPending} style={{
              padding: '12px 18px', minHeight: 44, borderRadius: 9, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', color: '#fff',
              boxShadow: '0 2px 8px rgba(99,102,241,0.3)', opacity: updateStatus.isPending ? 0.6 : 1,
            }}>
              {s.replace(/_/g, ' ')}
            </button>
          ))}
          {statusError && <span style={{ fontSize: 12, color: t.red }}>{statusError}</span>}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(['scoring', 'timeline', 'emails', 'notes'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={tabStyle(activeTab === tab)}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Scoring breakdown */}
      {activeTab === 'scoring' && (
        <div style={cardStyle}>
          <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Score Breakdown</div>
          {detail.scoring_breakdown?.factors?.length ? (
            <>
              {detail.scoring_breakdown.factors.map((factor, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 0', borderBottom: `1px solid ${t.border}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 14, color: factor.met ? t.green : t.textFaint }}>
                      {factor.met ? '✓' : '○'}
                    </span>
                    <span style={{ fontSize: 13, color: factor.met ? t.text : t.textMuted }}>{factor.label}</span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: factor.met ? t.green : t.textFaint }}>
                    {factor.met ? `+${factor.points}` : '0'} pts
                  </span>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 12, marginTop: 4 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Total Score</span>
                <span style={{ fontSize: 18, fontWeight: 800, color: bucketColor(lead.score_bucket, t) }}>
                  {detail.scoring_breakdown.total}
                </span>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: t.textMuted }}>
              {lead.score != null
                ? `Score: ${lead.score} (${lead.score_bucket || 'unclassified'}) — no breakdown available.`
                : 'No scoring data yet. The lead needs to submit the qualification form.'}
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {activeTab === 'timeline' && (
        <div style={cardStyle}>
          <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Event Timeline</div>
          {!detail.timeline?.length ? (
            <div style={{ fontSize: 13, color: t.textMuted }}>No events yet.</div>
          ) : (
            [...detail.timeline].reverse().map((event, i) => (
              <div key={event.id} style={{ display: 'flex', gap: 12, paddingBottom: 14, position: 'relative' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: t.accent, flexShrink: 0, marginTop: 3 }} />
                  {i < detail.timeline.length - 1 && (
                    <div style={{ width: 1, flex: 1, background: t.border, marginTop: 4 }} />
                  )}
                </div>
                <div style={{ flex: 1, paddingBottom: 4 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{event.event_type.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 11, color: t.textFaint, marginTop: 2 }}>{timeAgo(event.created_at)}</div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Rendered emails */}
      {activeTab === 'emails' && (
        <div>
          {!detail.rendered_emails?.length ? (
            <div style={{ ...cardStyle, fontSize: 13, color: t.textMuted }}>No emails generated yet.</div>
          ) : (
            detail.rendered_emails.map((email, i) => (
              <div key={i} style={cardStyle}>
                <div style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  {email.type.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.text, marginBottom: 10 }}>{email.subject}</div>
                <div style={{ fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{email.body}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Notes */}
      {activeTab === 'notes' && (
        <div>
          <form onSubmit={handleAddNote} style={{ ...cardStyle, display: 'flex', gap: 10 }}>
            <input
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Add a note…"
              style={{
                flex: 1, padding: '10px 14px', background: t.bgInput,
                border: `1.5px solid ${t.border}`, borderRadius: 10,
                fontSize: 13, color: t.text, outline: 'none',
              }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)}
              onBlur={e => (e.target.style.borderColor = t.border)}
            />
            <button type="submit" disabled={noteLoading || !noteText.trim()} style={{
              padding: '10px 18px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 600, color: '#fff',
              cursor: noteLoading || !noteText.trim() ? 'not-allowed' : 'pointer',
              opacity: noteLoading || !noteText.trim() ? 0.6 : 1,
            }}>
              {noteLoading ? '…' : 'Add'}
            </button>
          </form>

          {!detail.notes?.length ? (
            <div style={{ ...cardStyle, fontSize: 13, color: t.textMuted }}>No notes yet.</div>
          ) : (
            [...detail.notes].reverse().map((note, i) => (
              <div key={i} style={cardStyle}>
                <div style={{ fontSize: 13, color: t.text, lineHeight: 1.6 }}>{note.text}</div>
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 8 }}>{timeAgo(note.created_at)}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
