import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../../../api/agentApi';

interface LeadSource { id: number; name: string; description?: string; }

export const SourcesSettings: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['lead-sources'],
    queryFn: () => agentApi.get<{ sources: LeadSource[] }>('/agent/onboarding/sources'),
    retry: false,
  });

  const sources = data?.sources || [];
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Load selected once
  React.useEffect(() => {
    if (sources.length > 0 && selected.size === 0) {
      // In a real app we'd fetch the current enabled ones from a separate endpoint
      // but for now we follow the onboarding logic
      setSelected(new Set(sources.map(s => s.id)));
    }
  }, [sources]);

  const toggle = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    setError(''); setMsg(''); setLoading(true);
    try {
      await agentApi.put('/agent/onboarding/sources', { enabled_lead_source_ids: Array.from(selected) });
      setMsg('Settings saved');
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) return <div style={{ color: t.textMuted, fontSize: 13 }}>Loading…</div>;

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '24px' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16 }}>Lead Sources</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>Choose which lead sources you want to monitor.</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
          {sources.map(source => {
            const isOn = selected.has(source.id);
            return (
              <button
                key={source.id}
                onClick={() => toggle(source.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '12px 14px', borderRadius: 11, cursor: 'pointer',
                  background: isOn ? t.accentBg : t.bgCard,
                  border: `1.5px solid ${isOn ? t.accent : t.border}`,
                  transition: 'all 0.15s', textAlign: 'left',
                }}
              >
                <div style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                  background: isOn ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.bgInput,
                  border: `1.5px solid ${isOn ? 'transparent' : t.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, color: '#fff',
                }}>
                  {isOn ? '✓' : ''}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.text }}>{source.name}</div>
                </div>
              </button>
            );
          })}
        </div>

        {error && <div style={{ marginBottom: 14, color: t.red, fontSize: 13 }}>{error}</div>}
        {msg && <div style={{ marginBottom: 14, color: t.green, fontSize: 13 }}>{msg}</div>}

        <button onClick={handleSave} disabled={loading} style={{
          width: '100%', padding: '12px',
          background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}>
          {loading ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
