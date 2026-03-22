/**
 * Agent Lead Detail — premium lead command center.
 * Single continuous view, no tabs. Mobile-first.
 * Order: hero → actions → next-action → pipeline → timeline → scoring → emails → notes
 */

import React, { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import {
  useAgentLead, useUpdateLeadStatus, useAddLeadNote, useLeadPipeline,
} from '../hooks/useAgentQueries';
import { getAgentErrorMessage } from '../api/agentApi';
import { BackendPendingBadge } from '../components/BackendPendingBadge';

// ── CSS ───────────────────────────────────────────────────────────────────────

if (typeof document !== 'undefined' && !document.getElementById('ld-css')) {
  const s = document.createElement('style');
  s.id = 'ld-css';
  s.textContent = `
    /* Two-column desktop layout */
    .ld-body  { display: flex; gap: 14px; align-items: flex-start; }
    .ld-main  { flex: 1; min-width: 0; }
    .ld-aside { width: 244px; flex-shrink: 0; }
    /* Hero meta row */
    .ld-hero-meta { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    /* Desktop action bar — horizontal */
    .ld-acts  { display: flex; gap: 7px; flex-wrap: wrap; align-items: center; }
    /* Sticky bottom bar — hidden on desktop */
    .ld-sticky-bar { display: none; }

    @media (max-width: 767px) {
      /* Stack layout */
      .ld-body  { flex-direction: column; }
      .ld-aside { width: 100%; }

      /* Inline action bar hidden on mobile — replaced by sticky bar */
      .ld-acts-wrap { display: none; }

      /* Sticky bottom action bar */
      .ld-sticky-bar {
        display: flex;
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;
        padding: 8px 10px 16px;
        gap: 6px;
        background: var(--ld-bar-bg, #13141a);
        border-top: 1px solid var(--ld-bar-border, rgba(255,255,255,0.08));
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 -4px 24px rgba(0,0,0,0.35);
        align-items: stretch;
      }
      .ld-bar-btn {
        flex: 1;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 4px;
        padding: 8px 2px !important;
        border-radius: 11px;
        border: 1px solid transparent;
        cursor: pointer;
        font-size: 10px !important;
        font-weight: 700;
        letter-spacing: 0.01em;
        min-height: 54px;
        min-width: 0;
        text-decoration: none !important;
        transition: opacity 0.15s, transform 0.1s;
        box-sizing: border-box;
        line-height: 1;
      }
      .ld-bar-btn:active { transform: scale(0.93); }
      .ld-bar-btn .ld-bar-icon {
        font-size: 20px !important;
        line-height: 1;
        display: block;
      }
      .ld-bar-btn span:not(.ld-bar-icon) {
        font-size: 10px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
        display: block;
      }

      /* Extra bottom padding so content isn't hidden behind sticky bar */
      .ld-page { padding-bottom: 90px !important; }
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
  if (b === 'HOT')     return { label: 'HOT 🔥', color: '#f87171', bg: 'rgba(239,68,68,0.13)',  border: 'rgba(239,68,68,0.35)',  glow: 'rgba(239,68,68,0.08)' };
  if (b === 'WARM')    return { label: 'WARM',   color: '#fb923c', bg: 'rgba(251,146,60,0.13)', border: 'rgba(251,146,60,0.35)', glow: 'rgba(251,146,60,0.06)' };
  if (b === 'NURTURE') return { label: 'NURTURE',color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.25)',glow: 'transparent' };
  return null;
}

function evIcon(type: string): string {
  const u = type.toUpperCase();
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

// What should the agent do next given the current state?
function nextActionHint(state: string, pipeline?: { current_stage?: { name: string; category: string } }): { label: string; detail: string } | null {
  const stage = pipeline?.current_stage;
  if (stage) {
    const cat = stage.category.toLowerCase();
    if (cat === 'open' || cat === 'in_progress') return { label: `Follow up in ${stage.name}`, detail: 'Lead is active — reach out to move forward.' };
    if (cat === 'waiting') return { label: 'Waiting on lead', detail: 'No action needed until lead responds.' };
    if (cat === 'won') return { label: 'Lead closed — won', detail: 'This lead has been successfully converted.' };
    if (cat === 'lost') return { label: 'Lead closed — lost', detail: 'This lead was marked as lost.' };
  }
  if (state === 'NEW') return { label: 'Reach out to this lead', detail: 'New lead — contact them to start the process.' };
  if (state === 'INVITE_SENT') return { label: 'Follow up on form invite', detail: 'Form invite sent — check if they completed it.' };
  if (state === 'FORM_SUBMITTED') return { label: 'Review form submission', detail: 'Lead submitted the form — review and score.' };
  if (state === 'SCORED') return { label: 'Contact scored lead', detail: 'Lead has been scored — reach out now.' };
  if (state === 'CONTACTED') return { label: 'Schedule appointment', detail: 'Lead contacted — move toward setting an appointment.' };
  if (state === 'APPOINTMENT_SET') return { label: 'Confirm appointment', detail: 'Appointment set — confirm details with the lead.' };
  if (state === 'LOST') return { label: 'Re-engage or archive', detail: 'Lead was lost — consider re-engagement or close out.' };
  if (state === 'CLOSED') return null;
  return null;
}

// ── Primitives ────────────────────────────────────────────────────────────────

const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 14, padding: '16px 18px', marginBottom: 10, ...style }}>
      {children}
    </div>
  );
};

const SectionLabel: React.FC<{ children: React.ReactNode; aside?: React.ReactNode }> = ({ children, aside }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.9px' }}>
        {children}
      </span>
      {aside}
    </div>
  );
};



const Btn: React.FC<{
  icon: string; label: string; href?: string;
  disabled?: boolean; pending?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost' | 'green';
  onClick?: () => void; title?: string; small?: boolean;
}> = ({ icon, label, href, disabled, pending, variant = 'secondary', onClick, title, small }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hov, setHov] = useState(false);
  const off = disabled || pending;
  const pad = small ? '7px 12px' : '9px 15px';
  const fz = small ? 12 : 13;

  const base: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: pad, borderRadius: 9, fontSize: fz, fontWeight: 600,
    cursor: off ? 'not-allowed' : 'pointer', transition: 'all 0.15s',
    textDecoration: 'none', border: 'none', opacity: off ? 0.45 : 1, flexShrink: 0,
    ...(variant === 'primary' ? {
      background: hov && !off ? 'linear-gradient(135deg,#5558e8,#7c4fe0)' : 'linear-gradient(135deg,#6366f1,#8b5cf6)',
      color: '#fff', boxShadow: off ? 'none' : '0 2px 8px rgba(99,102,241,0.35)',
    } : variant === 'green' ? {
      background: hov && !off ? t.greenBg : 'transparent',
      color: t.green, border: `1px solid ${hov && !off ? t.green + '50' : t.border}`,
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
      <span style={{ fontSize: fz + 1 }}>{icon}</span>
      <span>{label}</span>
      {pending && <BackendPendingBadge variant="inline" tooltip="Not yet supported" />}
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

// ── Stepper track (scrollable, arrow-navigable) ───────────────────────────────

const STAGE_W = 104; // px per stage slot — bigger, more presence

// Inject pulse keyframe once
if (typeof document !== 'undefined' && !document.getElementById('stepper-css')) {
  const s = document.createElement('style');
  s.id = 'stepper-css';
  s.textContent = `
    @keyframes stepper-pulse {
      0%   { box-shadow: 0 0 0 0 var(--sp-c), 0 0 14px var(--sp-c); }
      50%  { box-shadow: 0 0 0 8px transparent, 0 0 26px var(--sp-c); }
      100% { box-shadow: 0 0 0 0 var(--sp-c), 0 0 14px var(--sp-c); }
    }
    .stepper-cur { animation: stepper-pulse 2.2s ease-in-out infinite; }
    .stepper-scroll::-webkit-scrollbar { display: none; }
  `;
  document.head.appendChild(s);
}

const StepperTrack: React.FC<{
  stages: NonNullable<ReturnType<typeof useLeadPipeline>['data']>['stages'];
  curIdx: number;
  cur: NonNullable<ReturnType<typeof useLeadPipeline>['data']>['current_stage'];
}> = ({ stages, curIdx, cur }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  const updateArrows = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 4);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || curIdx < 0) return;
    const targetX = curIdx * STAGE_W - el.clientWidth / 2 + STAGE_W / 2;
    el.scrollTo({ left: Math.max(0, targetX), behavior: 'smooth' });
    setTimeout(updateArrows, 350);
  }, [curIdx]);

  useEffect(() => { setTimeout(updateArrows, 100); }, [stages.length]);

  const scroll = (dir: 'left' | 'right') => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === 'left' ? -STAGE_W * 3 : STAGE_W * 3, behavior: 'smooth' });
    setTimeout(updateArrows, 350);
  };

  const totalW = stages.length * STAGE_W;
  const needsScroll = stages.length > 4;

  return (
    <div style={{ padding: '4px 0 20px', position: 'relative' }}>
      {/* Left arrow + fade */}
      {needsScroll && canLeft && (
        <button onClick={() => scroll('left')} style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 44, zIndex: 3,
          background: `linear-gradient(90deg, ${t.bgCard} 50%, transparent)`,
          border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'flex-start',
          paddingLeft: 6, color: t.textSecondary, fontSize: 22, fontWeight: 300,
        }}>‹</button>
      )}
      {/* Right arrow + fade */}
      {needsScroll && canRight && (
        <button onClick={() => scroll('right')} style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width: 44, zIndex: 3,
          background: `linear-gradient(270deg, ${t.bgCard} 50%, transparent)`,
          border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
          paddingRight: 6, color: t.textSecondary, fontSize: 22, fontWeight: 300,
        }}>›</button>
      )}

      {/* Scrollable track */}
      <div
        ref={scrollRef}
        onScroll={updateArrows}
        className="stepper-scroll"
        style={{ overflowX: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        <div style={{
          display: 'flex', alignItems: 'center',
          width: totalW, minWidth: totalW,
          padding: '10px 0 6px',
        }}>
          {stages.map((stage, idx) => {
            const isCur = stage.id === cur?.id;
            const isPast = curIdx >= 0 && idx < curIdx;
            const isFuture = curIdx >= 0 && idx > curIdx;
            const lineColor = isPast ? t.green : t.border;

            return (
              <React.Fragment key={stage.id}>
                {/* Stage node column */}
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  gap: 7, flexShrink: 0, width: STAGE_W,
                  opacity: isFuture ? 0.38 : 1,
                  transition: 'opacity 0.25s',
                }}>
                  {/* Dot */}
                  <div
                    className={isCur ? 'stepper-cur' : undefined}
                    style={{
                      '--sp-c': stage.color,
                      width: isCur ? 28 : isPast ? 22 : 16,
                      height: isCur ? 28 : isPast ? 22 : 16,
                      borderRadius: '50%',
                      background: isCur
                        ? `radial-gradient(circle at 38% 32%, ${stage.color}dd, ${stage.color})`
                        : isPast ? t.green : t.bgBadge,
                      border: isCur
                        ? `2.5px solid ${stage.color}`
                        : isPast ? `2px solid ${t.green}` : `2px solid ${t.border}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: isCur ? 12 : 9,
                      color: isCur || isPast ? '#fff' : t.textFaint,
                      fontWeight: 800,
                      transition: 'width 0.2s, height 0.2s',
                      flexShrink: 0,
                    } as React.CSSProperties}
                  >
                    {isPast ? '✓' : isCur ? '●' : ''}
                  </div>

                  {/* Stage name */}
                  <div style={{
                    fontSize: isCur ? 11 : 10,
                    textAlign: 'center',
                    width: STAGE_W - 8,
                    lineHeight: 1.35,
                    color: isCur ? stage.color : isPast ? t.textSecondary : t.textFaint,
                    fontWeight: isCur ? 800 : isPast ? 600 : 400,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    padding: '0 4px',
                    transition: 'color 0.2s',
                  }}>
                    {stage.is_closed_won ? '✓ ' : stage.is_closed_lost ? '✗ ' : ''}{stage.name}
                  </div>

                  {/* HERE pill */}
                  {isCur && (
                    <div style={{
                      fontSize: 8, fontWeight: 800, letterSpacing: '0.09em',
                      padding: '2px 7px', borderRadius: 4,
                      background: `${stage.color}22`,
                      color: stage.color,
                      border: `1px solid ${stage.color}45`,
                      marginTop: -3,
                    }}>HERE</div>
                  )}
                </div>

                {/* Connector line */}
                {idx < stages.length - 1 && (
                  <div style={{
                    flex: 1, height: 3,
                    marginBottom: isCur ? 32 : isPast ? 16 : 16,
                    minWidth: 6, borderRadius: 2,
                    background: lineColor,
                    transition: 'background 0.3s',
                    position: 'relative', overflow: 'hidden',
                  }}>
                    {idx === curIdx && (
                      <div style={{
                        position: 'absolute', top: 0, left: 0,
                        height: '100%', width: '50%',
                        background: `linear-gradient(90deg, ${stage.color}cc, transparent)`,
                        borderRadius: 2,
                      }} />
                    )}
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ── Pipeline section ──────────────────────────────────────────────────────────

const PipelineSection: React.FC<{
  pipeline: NonNullable<ReturnType<typeof useLeadPipeline>['data']>;
}> = ({ pipeline }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  // No pipeline configured for this company yet
  if (!pipeline.pipeline_name || pipeline.stages.length === 0) {
    return (
      <Card>
        <SectionLabel aside={<BackendPendingBadge tooltip="No active pipeline configured for this company" />}>
          Pipeline
        </SectionLabel>
        <div style={{
          padding: '20px 0', textAlign: 'center',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: t.bgBadge, border: `1px dashed ${t.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
          }}>⬡</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: t.textMuted }}>No pipeline assigned</div>
          <div style={{ fontSize: 12, color: t.textFaint, maxWidth: 260 }}>
            Configure a pipeline in the admin panel to track this lead through stages.
          </div>
        </div>
      </Card>
    );
  }

  const sorted = [...pipeline.stages].sort((a, b) => a.position - b.position);
  const curIdx = sorted.findIndex(s => s.id === pipeline.current_stage?.id);
  const cur = pipeline.current_stage;
  const nextStage = curIdx >= 0 && curIdx < sorted.length - 1 ? sorted[curIdx + 1] : null;
  const completedCount = curIdx > 0 ? curIdx : 0;
  const totalCount = sorted.length;

  // Category icon — reserved for future use
  // const catIcon = ...

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 18px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.9px', marginBottom: 3 }}>
              Pipeline
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{pipeline.pipeline_name}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: t.textFaint }}>
              Step <span style={{ fontWeight: 700, color: t.text }}>{curIdx >= 0 ? curIdx + 1 : '—'}</span> of {totalCount}
            </div>
            {completedCount > 0 && (
              <div style={{ fontSize: 10, color: t.green, marginTop: 1 }}>{completedCount} completed</div>
            )}
          </div>
        </div>
      </div>

      {/* Current stage hero */}
      {cur && (
        <div style={{
          margin: '0 18px 16px',
          padding: '14px 16px',
          borderRadius: 12,
          background: `${cur.color}12`,
          border: `1.5px solid ${cur.color}35`,
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          {/* Stage color dot + icon */}
          <div style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            background: `${cur.color}20`,
            border: `2px solid ${cur.color}50`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, color: cur.color,
            boxShadow: `0 0 12px ${cur.color}25`,
          }}>
            {cur.is_closed_won ? '✓' : cur.is_closed_lost ? '✗' : '▶'}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: cur.color, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>
              Current Stage
            </div>
            <div style={{ fontSize: 16, fontWeight: 800, color: t.text, lineHeight: 1.2 }}>{cur.name}</div>
            <div style={{ fontSize: 11, color: t.textMuted, marginTop: 3, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={{
                padding: '1px 7px', borderRadius: 4,
                background: `${cur.color}15`, color: cur.color,
                border: `1px solid ${cur.color}30`, fontWeight: 600,
              }}>
                {cur.category.replace(/_/g, ' ')}
              </span>
              {pipeline.stage_entered_at && (
                <span style={{ color: t.textFaint }}>entered {timeAgo(pipeline.stage_entered_at)}</span>
              )}
            </div>
          </div>
          {/* Next stage hint */}
          {nextStage && (
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontSize: 9, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Next</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: t.textMuted }}>{nextStage.name}</div>
            </div>
          )}
        </div>
      )}

      {/* Stage stepper track — scrollable, auto-centers on current stage */}
      <StepperTrack stages={sorted} curIdx={curIdx} cur={cur} />

      {/* Stage history */}
      {pipeline.stage_history.length > 0 && (
        <div style={{ borderTop: `1px solid ${t.border}`, padding: '12px 18px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.9px', marginBottom: 10 }}>
            Stage History
          </div>
          {[...pipeline.stage_history].reverse().slice(0, 4).map((h, i, arr) => {
            const st = sorted.find(s => s.id === h.to_stage_id);
            return (
              <div key={h.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: i < arr.length - 1 ? `1px solid ${t.border}` : 'none',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {st && (
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: st.color, flexShrink: 0,
                      boxShadow: `0 0 4px ${st.color}60`,
                    }} />
                  )}
                  <span style={{ fontSize: 12, fontWeight: 600, color: t.text }}>{st?.name || `Stage ${h.to_stage_id}`}</span>
                  <span style={{
                    fontSize: 10, color: t.textFaint,
                    background: t.bgBadge, padding: '1px 6px', borderRadius: 4,
                    border: `1px solid ${t.border}`,
                  }}>{h.change_source.replace(/_/g, ' ')}</span>
                </div>
                <span style={{ fontSize: 11, color: t.textFaint, flexShrink: 0 }}>{timeAgo(h.created_at)}</span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};

// ── Timeline section ──────────────────────────────────────────────────────────

const TimelineSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [showAll, setShowAll] = useState(false);
  const events = [...(detail.timeline || [])].reverse();
  const visible = showAll ? events : events.slice(0, 7);

  return (
    <Card>
      <SectionLabel aside={
        events.length > 0 && (
          <span style={{ fontSize: 11, color: t.textFaint, background: t.bgBadge, padding: '2px 7px', borderRadius: 5 }}>
            {events.length}
          </span>
        )
      }>Activity Timeline</SectionLabel>

      {!events.length ? (
        <div style={{ padding: '16px 0', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 22, marginBottom: 6 }}>◎</div>
          No activity recorded yet
        </div>
      ) : (
        <>
          {visible.map((ev, i) => {
            const color = evColor(ev.event_type, t);
            const icon = evIcon(ev.event_type);
            const isLast = i === visible.length - 1;
            return (
              <div key={ev.id} style={{ display: 'flex', gap: 11 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 24 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                    background: `${color}14`, border: `1.5px solid ${color}40`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, color, zIndex: 1,
                  }}>{icon}</div>
                  {!isLast && <div style={{ width: 1, flex: 1, minHeight: 10, background: t.border, margin: '2px 0' }} />}
                </div>
                <div style={{ flex: 1, paddingBottom: isLast ? 0 : 12 }}>
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
          {events.length > 7 && (
            <button onClick={() => setShowAll(v => !v)} style={{
              marginTop: 6, background: 'none', border: 'none', cursor: 'pointer',
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

// ── Scoring section ───────────────────────────────────────────────────────────

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
      <SectionLabel>Qualification Score</SectionLabel>
      {bd?.factors?.length ? (() => {
        const max = bd.factors.reduce((s, f) => s + f.points, 0);
        const pct = max > 0 ? Math.round((bd.total / max) * 100) : 0;
        return (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14,
              padding: '12px 14px', borderRadius: 10,
              background: bc ? bc.bg : t.bgBadge, border: `1px solid ${bc ? bc.border : t.border}`,
            }}>
              <div style={{ textAlign: 'center', flexShrink: 0 }}>
                <div style={{ fontSize: 32, fontWeight: 800, color: bc?.color || t.text, lineHeight: 1 }}>{bd.total}</div>
                <div style={{ fontSize: 10, color: t.textFaint, marginTop: 1 }}>/ {max}</div>
              </div>
              <div style={{ flex: 1 }}>
                {bc && <div style={{ fontSize: 12, fontWeight: 700, color: bc.color, marginBottom: 4 }}>{bc.label}</div>}
                <div style={{ height: 5, borderRadius: 3, background: t.border, overflow: 'hidden' }}>
                  <div style={{ height: '100%', borderRadius: 3, width: `${pct}%`, background: bc?.color || t.accent, transition: 'width 0.5s ease' }} />
                </div>
                <div style={{ fontSize: 10, color: t.textFaint, marginTop: 3 }}>{pct}% of max score</div>
              </div>
            </div>
            {bd.factors.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 0', borderBottom: i < bd.factors.length - 1 ? `1px solid ${t.border}` : 'none',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                    background: f.met ? t.greenBg : t.bgBadge,
                    border: `1.5px solid ${f.met ? t.green : t.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 9, color: f.met ? t.green : t.textFaint,
                  }}>{f.met ? '✓' : '○'}</div>
                  <span style={{ fontSize: 13, color: f.met ? t.text : t.textMuted }}>{f.label}</span>
                </div>
                <span style={{
                  fontSize: 12, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
                  color: f.met ? t.green : t.textFaint, background: f.met ? t.greenBg : 'transparent',
                }}>{f.met ? `+${f.points}` : '—'}</span>
              </div>
            ))}
          </>
        );
      })() : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0' }}>
          <div style={{ fontSize: 26 }}>📋</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>
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

// ── Emails section ────────────────────────────────────────────────────────────

const EmailsSection: React.FC<{
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
}> = ({ detail }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [expanded, setExpanded] = useState<number | null>(null);
  const emails = detail.rendered_emails || [];

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '16px 18px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.9px' }}>
          Emails Sent
        </span>
        {emails.length > 0 && (
          <span style={{ fontSize: 11, color: t.textFaint, background: t.bgBadge, padding: '2px 7px', borderRadius: 5 }}>
            {emails.length}
          </span>
        )}
      </div>
      {!emails.length ? (
        <div style={{ padding: '0 18px 18px', textAlign: 'center', color: t.textMuted, fontSize: 13 }}>
          <div style={{ fontSize: 20, marginBottom: 5 }}>✉</div>
          No emails sent yet
        </div>
      ) : emails.map((email, i) => (
        <div key={i} style={{ borderTop: `1px solid ${t.border}` }}>
          <button
            onClick={() => setExpanded(expanded === i ? null : i)}
            style={{
              width: '100%', padding: '12px 18px', background: 'none', border: 'none',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
              <span style={{ fontSize: 13, flexShrink: 0, color: t.accent }}>✉</span>
              <div style={{ minWidth: 0, textAlign: 'left' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: t.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {email.subject}
                </div>
                <div style={{ fontSize: 11, color: t.textFaint, marginTop: 1 }}>
                  {email.type.replace(/_/g, ' ')}{email.sent_at && ` · ${timeAgo(email.sent_at)}`}
                </div>
              </div>
            </div>
            <span style={{ color: t.textFaint, fontSize: 10, flexShrink: 0 }}>{expanded === i ? '▲' : '▼'}</span>
          </button>
          {expanded === i && (
            <div style={{ padding: '0 18px 14px', borderTop: `1px solid ${t.border}` }}>
              <div style={{ paddingTop: 10, fontSize: 13, color: t.textSecondary, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                {email.body}
              </div>
            </div>
          )}
        </div>
      ))}
    </Card>
  );
};

// ── Notes section ─────────────────────────────────────────────────────────────

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
      <SectionLabel>Internal Notes</SectionLabel>
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: notes.length ? 14 : 0 }}>
        <textarea
          value={text} onChange={e => setText(e.target.value)}
          placeholder="Add a note visible only to your team…" rows={2}
          style={{
            flex: 1, padding: '9px 12px', background: t.bgInput,
            border: `1.5px solid ${t.border}`, borderRadius: 9,
            fontSize: 13, color: t.text, outline: 'none', resize: 'vertical',
            fontFamily: 'inherit', lineHeight: 1.5,
          }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)}
          onBlur={e => (e.target.style.borderColor = t.border)}
        />
        <button type="submit" disabled={saving || !text.trim()} style={{
          padding: '9px 15px', background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
          border: 'none', borderRadius: 9, fontSize: 13, fontWeight: 600, color: '#fff',
          cursor: saving || !text.trim() ? 'not-allowed' : 'pointer',
          opacity: saving || !text.trim() ? 0.6 : 1, alignSelf: 'flex-start',
        }}>{saving ? '…' : 'Add'}</button>
      </form>
      {notes.map((n, i) => (
        <div key={i} style={{ padding: '10px 0', borderTop: `1px solid ${t.border}` }}>
          <div style={{ fontSize: 13, color: t.text, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{n.text}</div>
          <div style={{ fontSize: 11, color: t.textFaint, marginTop: 5 }}>{timeAgo(n.created_at)}</div>
        </div>
      ))}
      {!notes.length && (
        <div style={{ fontSize: 12, color: t.textFaint, paddingTop: notes.length ? 0 : 8 }}>No notes yet</div>
      )}
    </Card>
  );
};

// ── Sidebar ───────────────────────────────────────────────────────────────────

const Sidebar: React.FC<{
  lead: NonNullable<ReturnType<typeof useAgentLead>['data']>['lead'];
  detail: NonNullable<ReturnType<typeof useAgentLead>['data']>;
  stageName: string;
  currentState: string;
}> = ({ lead, detail, stageName, currentState }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const bc = bucketCfg(lead.score_bucket);
  const emailCount = detail.rendered_emails?.length || 0;
  const factors = detail.scoring_breakdown?.factors || [];

  return (
    <>
      {/* Lead facts */}
      <Card>
        <SectionLabel>Lead</SectionLabel>
        {[
          { label: 'Status',  value: currentState.replace(/_/g, ' ') },
          { label: 'Stage',   value: stageName },
          { label: 'Score',   value: lead.score != null ? `${lead.score} pts` : '—', color: bc?.color },
          { label: 'Bucket',  value: lead.score_bucket || '—', color: bc?.color },
          { label: 'Source',  value: lead.source || '—' },
          { label: 'Created', value: timeAgo(lead.created_at) },
          ...(lead.last_agent_action_at ? [{ label: 'Last action', value: timeAgo(lead.last_agent_action_at) }] : []),
        ].map((r, i, arr) => (
          <div key={r.label} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '5px 0', borderBottom: i < arr.length - 1 ? `1px solid ${t.border}` : 'none',
          }}>
            <span style={{ fontSize: 11, color: t.textFaint }}>{r.label}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: r.color || t.text, textAlign: 'right', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.value}</span>
          </div>
        ))}
      </Card>

      {/* Qualification checklist */}
      <Card>
        <SectionLabel>Qualification</SectionLabel>
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

      {/* Communications */}
      <Card>
        <SectionLabel>Communications</SectionLabel>
        <div style={{ fontSize: 12, color: t.textMuted, marginBottom: 8 }}>
          {emailCount ? `${emailCount} email${emailCount !== 1 ? 's' : ''} sent` : 'No emails sent yet'}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '7px 9px', borderRadius: 7, background: t.bgBadge, border: `1px dashed ${t.border}`,
        }}>
          <span style={{ fontSize: 11, color: t.textFaint }}>SMS & call log</span>
          <BackendPendingBadge tooltip="SMS and call log — coming soon" />
        </div>
      </Card>

      {/* Documents */}
      <Card>
        <SectionLabel aside={<BackendPendingBadge tooltip="Document uploads — coming soon" />}>
          Documents
        </SectionLabel>
        <div style={{
          padding: '12px', borderRadius: 8, background: t.bgBadge,
          border: `1px dashed ${t.border}`, textAlign: 'center',
        }}>
          <div style={{ fontSize: 20, marginBottom: 4 }}>📄</div>
          <div style={{ fontSize: 11, color: t.textFaint }}>No documents yet</div>
        </div>
      </Card>
    </>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────

export function AgentLeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const t = getTokens(theme);
  const leadId = Number(id);

  const { data: detail, isLoading, error } = useAgentLead(leadId);
  const { data: pipeline } = useLeadPipeline(leadId);
  const updateStatus = useUpdateLeadStatus();

  const [statusErr, setStatusErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (isLoading) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>⟳</div>
        Loading lead…
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: t.textMuted }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>⚠</div>
        {error ? getAgentErrorMessage(error) : 'Lead not found'}
        <div style={{ marginTop: 12 }}>
          <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: t.accent, cursor: 'pointer', fontSize: 13 }}>
            ← Back
          </button>
        </div>
      </div>
    );
  }

  const lead = detail.lead;
  const bc = bucketCfg(lead.score_bucket);
  const currentState = lead.current_state || 'NEW';
  const nextStates = TRANSITIONS[currentState] || [];
  const stageName = pipeline?.current_stage?.name || '—';
  const nextAction = nextActionHint(currentState, pipeline);
  const isAging = lead.is_aging;

  const copyPhone = () => {
    if (!lead.phone) return;
    navigator.clipboard.writeText(lead.phone).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  const moveToState = async (status: string) => {
    setStatusErr(null);
    try { await updateStatus.mutateAsync({ id: leadId, status }); }
    catch (e) { setStatusErr(getAgentErrorMessage(e)); }
  };

  // Accent color for the hero strip — bucket color or a neutral
  const accentColor = bc?.color ?? t.accent;

  // CSS variable values for sticky bar theming
  const barBg = theme === 'dark' ? '#13141a' : '#ffffff';
  const barBorder = theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.1)';

  return (
    <div
      className="ld-page"
      style={{ maxWidth: 1100, margin: '0 auto', padding: '16px 14px 48px' }}
    >
      {/* Back link */}
      <button onClick={() => navigate(-1)} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        color: t.textFaint, fontSize: 12, padding: '0 0 12px',
        display: 'inline-flex', alignItems: 'center', gap: 5,
        letterSpacing: '0.02em', fontWeight: 500,
        minHeight: 36,
      }}>
        <span style={{ fontSize: 14 }}>←</span> All Leads
      </button>

      {/* ── Hero card ── */}
      <div style={{
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 18, marginBottom: 8, overflow: 'hidden',
      }}>
        {/* Colored top accent bar */}
        <div style={{
          height: 4,
          background: bc
            ? `linear-gradient(90deg, ${bc.color}, ${bc.color}88)`
            : `linear-gradient(90deg, ${t.accent}, ${t.accent}55)`,
        }} />
        <div style={{ padding: '18px 16px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            {/* Avatar */}
            <div style={{
              width: 54, height: 54, borderRadius: 15, flexShrink: 0,
              background: avatarGrad(lead.name),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 19, fontWeight: 800, color: '#fff', letterSpacing: '-0.5px',
              boxShadow: `0 4px 14px ${accentColor}30`,
            }}>
              {initials(lead.name)}
            </div>

            {/* Identity block */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* Name + aging */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 5 }}>
                <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: t.text, lineHeight: 1.15, letterSpacing: '-0.3px' }}>
                  {lead.name}
                </h1>
                {isAging && (
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
                    background: 'rgba(251,146,60,0.15)', color: '#fb923c',
                    border: '1px solid rgba(251,146,60,0.35)', letterSpacing: '0.04em',
                  }}>⏱ AGING</span>
                )}
              </div>

              {/* Contact row */}
              <div className="ld-hero-meta" style={{ marginBottom: 10 }}>
                {lead.phone && (
                  <a href={`tel:${lead.phone}`} style={{
                    fontSize: 13, fontWeight: 600, color: t.accent,
                    textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
                  }}>📞 {lead.phone}</a>
                )}
                {lead.email && (
                  <a href={`mailto:${lead.email}`} style={{
                    fontSize: 13, color: t.textSecondary,
                    textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
                  }}>✉ {lead.email}</a>
                )}
                {lead.source && (
                  <span style={{ fontSize: 12, color: t.textFaint }}>
                    via <span style={{ color: t.textMuted, fontWeight: 500 }}>{lead.source}</span>
                  </span>
                )}
                <span style={{ fontSize: 12, color: t.textFaint }}>Added {timeAgo(lead.created_at)}</span>
              </div>

              {/* Badges */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {bc && (
                  <span style={{
                    fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 7,
                    background: bc.bg, color: bc.color, border: `1.5px solid ${bc.border}`,
                    letterSpacing: '0.05em',
                  }}>{bc.label}</span>
                )}
                {lead.score != null && (
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 7,
                    background: t.bgBadge, color: t.textSecondary, border: `1px solid ${t.border}`,
                  }}>⭐ {lead.score} pts</span>
                )}
                {pipeline?.current_stage ? (
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 7,
                    background: `${pipeline.current_stage.color}18`,
                    color: pipeline.current_stage.color,
                    border: `1.5px solid ${pipeline.current_stage.color}40`,
                  }}>📍 {pipeline.current_stage.name}</span>
                ) : (
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 7,
                    background: t.bgBadge, color: t.textMuted, border: `1px solid ${t.border}`,
                  }}>🔄 {currentState.replace(/_/g, ' ')}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Next Action callout ── */}
      {nextAction && (
        <div style={{
          marginBottom: 8,
          background: bc ? bc.bg : `${t.accent}0d`,
          border: `1.5px solid ${bc ? bc.border : t.accent + '30'}`,
          borderRadius: 14, padding: '13px 16px',
          display: 'flex', alignItems: 'center', gap: 13,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 11, flexShrink: 0,
            background: bc ? `${bc.color}20` : `${t.accent}18`,
            border: `1.5px solid ${bc ? bc.border : t.accent + '35'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
          }}>⚡</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
              color: bc?.color ?? t.accent, textTransform: 'uppercase', marginBottom: 3,
            }}>Recommended Action</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: t.text, lineHeight: 1.3 }}>
              {nextAction.label}
            </div>
            <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>{nextAction.detail}</div>
          </div>
        </div>
      )}

      {/* ── Desktop action bar (hidden on mobile — replaced by sticky bar) ── */}
      <div className="ld-acts-wrap" style={{
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 14, padding: '12px 16px', marginBottom: 12,
      }}>
        <div className="ld-acts">
          {lead.phone && <Btn icon="📞" label="Call" href={`tel:${lead.phone}`} variant="primary" />}
          {lead.email && <Btn icon="✉" label="Email" href={`mailto:${lead.email}`} variant="secondary" />}
          {lead.phone && <Btn icon={copied ? '✓' : '📋'} label={copied ? 'Copied!' : 'Copy #'} onClick={copyPhone} variant="secondary" />}
          <Btn icon="💬" label="Text" pending variant="secondary" />
          {nextStates.length > 0 && (
            <>
              <div style={{ width: 1, height: 26, background: t.border, margin: '0 6px', flexShrink: 0 }} />
              {nextStates.map(s => (
                <Btn key={s} icon="→" label={s.replace(/_/g, ' ')} onClick={() => moveToState(s)} variant="ghost" small />
              ))}
            </>
          )}
        </div>
        {statusErr && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#f87171', display: 'flex', alignItems: 'center', gap: 5 }}>
            <span>⚠</span> {statusErr}
          </div>
        )}
      </div>

      {/* ── Two-column body ── */}
      <div className="ld-body">
        <div className="ld-main">
          {pipeline && <PipelineSection pipeline={pipeline} />}
          {!pipeline && (
            <Card>
              <SectionLabel>Pipeline</SectionLabel>
              <div style={{ padding: '16px 0', textAlign: 'center', color: t.textFaint, fontSize: 13 }}>Loading pipeline…</div>
            </Card>
          )}
          <TimelineSection detail={detail} />
          <ScoringSection detail={detail} />
          <EmailsSection detail={detail} />
          <NotesSection detail={detail} leadId={leadId} />
        </div>
        <div className="ld-aside">
          <Sidebar lead={lead} detail={detail} stageName={stageName} currentState={currentState} />
        </div>
      </div>

      {/* ── Sticky mobile bottom action bar ── */}
      <div
        className="ld-sticky-bar"
        style={{ '--ld-bar-bg': barBg, '--ld-bar-border': barBorder } as React.CSSProperties}
      >
        {/* Call */}
        {lead.phone ? (
          <a href={`tel:${lead.phone}`} className="ld-bar-btn" style={{
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff',
          }}>
            <span className="ld-bar-icon">📞</span>
            <span>Call</span>
          </a>
        ) : (
          <span className="ld-bar-btn" style={{ background: t.bgBadge, color: t.textFaint, opacity: 0.4 }}>
            <span className="ld-bar-icon">📞</span><span>Call</span>
          </span>
        )}

        {/* Email */}
        {lead.email ? (
          <a href={`mailto:${lead.email}`} className="ld-bar-btn" style={{
            background: t.bgCardHover, color: t.text, borderColor: t.border,
          }}>
            <span className="ld-bar-icon">✉</span>
            <span>Email</span>
          </a>
        ) : (
          <span className="ld-bar-btn" style={{ background: t.bgBadge, color: t.textFaint, opacity: 0.4 }}>
            <span className="ld-bar-icon">✉</span><span>Email</span>
          </span>
        )}

        {/* Text — backend pending */}
        <span className="ld-bar-btn" style={{ background: t.bgBadge, color: t.textFaint, opacity: 0.45, cursor: 'not-allowed' }}>
          <span className="ld-bar-icon">💬</span>
          <span>Text</span>
        </span>

        {/* Copy phone */}
        {lead.phone && (
          <button className="ld-bar-btn" onClick={copyPhone} style={{
            background: copied ? `${t.green}18` : t.bgCardHover,
            color: copied ? t.green : t.textMuted,
            borderColor: copied ? `${t.green}40` : t.border,
          }}>
            <span className="ld-bar-icon">{copied ? '✓' : '📋'}</span>
            <span>{copied ? 'Copied' : 'Copy #'}</span>
          </button>
        )}

        {/* Stage move */}
        {nextStates.length > 0 && (
          <button className="ld-bar-btn" onClick={() => moveToState(nextStates[0])} style={{
            background: t.bgCardHover, color: t.textSecondary, borderColor: t.border,
          }}>
            <span className="ld-bar-icon">→</span>
            <span>{nextStates[0].replace(/_/g, ' ')}</span>
          </button>
        )}
      </div>

    </div>
  );
}
