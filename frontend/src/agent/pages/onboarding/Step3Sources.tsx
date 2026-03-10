/**
 * Step 3 — Lead Sources: checklist of platform lead sources, default all enabled.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '../../../contexts/ThemeContext';
import { getTokens } from '../../../utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

interface LeadSource { id: number; name: string; description?: string; }
interface Props { goBack: () => void; }

export const Step3Sources: React.FC<Props> = ({ goBack }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['lead-sources'],
    queryFn: () => agentApi.get<{ sources: LeadSource[] }>('/lead-sources'),
  });

  const sources = data?.sources || [];
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Default all enabled once loaded
  React.useEffect(() => {
    if (sources.length > 0 && selected.size === 0) {
      setSelected(new Set(sources.map(s => s.id)));
    }
  }, [sources]);

  const toggle = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    setError(''); setLoading(true);
    try {
      await agentApi.put('/agent/onboarding/sources', { enabled_lead_source_ids: Array.from(selected) });
      navigate('/agent/onboarding/automation');
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 22, padding: '36px 32px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: t.text, letterSpacing: '-0.4px', marginBottom: 6 }}>Lead Sources</div>
        <div style={{ fontSize: 13, color: t.textMuted }}>Choose which lead sources you want to monitor. All are enabled by default.</div>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: t.textMuted, fontSize: 13 }}>Loading sources…</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
          {sources.map(source => {
            const isOn = selected.has(source.id);
            return (
              <button
                key={source.id}
                type="button"
                onClick={() => toggle(source.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
                  background: isOn ? t.accentBg : t.bgCard,
                  border: `1.5px solid ${isOn ? t.accent : t.border}`,
                  transition: 'all 0.15s', textAlign: 'left',
                }}
              >
                <div style={{
                  width: 20, height: 20, borderRadius: 6, flexShrink: 0,
                  background: isOn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgInput,
                  border: `1.5px solid ${isOn ? 'transparent' : t.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, color: '#fff',
                }}>
                  {isOn ? '✓' : ''}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: t.text }}>{source.name}</div>
                  {source.description && <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>{source.description}</div>}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <button type="button" onClick={goBack} style={{
          flex: 1, padding: '12px', background: t.bgCard, border: `1px solid ${t.border}`,
          borderRadius: 11, fontSize: 14, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
        }}>Back</button>
        <button type="button" onClick={handleSubmit} disabled={loading || selected.size === 0} style={{
          flex: 2, padding: '12px',
          background: loading || selected.size === 0 ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
          cursor: loading || selected.size === 0 ? 'not-allowed' : 'pointer',
          boxShadow: loading || selected.size === 0 ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
        }}>
          {loading ? 'Saving…' : `Continue (${selected.size} selected)`}
        </button>
      </div>
    </div>
  );
};
