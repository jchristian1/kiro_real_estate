/**
 * Sources Settings — manage which lead sources are monitored.
 */

import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTheme } from '../../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../../shared/utils/theme';
import { agentApi, getAgentErrorMessage } from '../../api/agentApi';

interface LeadSource { id: number; name: string; description?: string; }

export const SourcesSettingsPage: React.FC = () => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['agent-sources'],
    queryFn: () => agentApi.get<{ sources: LeadSource[] }>('/agent/onboarding/sources'),
    retry: false,
  });

  const sources = data?.sources || [];
  const [selected, setSelected] = useState<Set<number> | null>(null);

  // Load saved preferences
  const { data: prefsData } = useQuery({
    queryKey: ['agent-source-prefs'],
    queryFn: () => agentApi.get<{ enabled_lead_source_ids: number[] }>('/agent/settings/sources'),
    retry: false,
  });

  // Once both sources and prefs are loaded, initialise selection
  React.useEffect(() => {
    if (sources.length > 0 && selected === null) {
      if (prefsData?.enabled_lead_source_ids) {
        setSelected(new Set(prefsData.enabled_lead_source_ids));
      } else {
        // Default: all enabled
        setSelected(new Set(sources.map(s => s.id)));
      }
    }
  }, [sources, prefsData]);

  const toggle = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev ?? []);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  };

  const flash = (text: string, type: 'ok' | 'err') => {
    setMsg(text); setMsgType(type);
    setTimeout(() => setMsg(''), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await agentApi.put('/agent/onboarding/sources', {
        enabled_lead_source_ids: Array.from(selected ?? []),
      });
      qc.invalidateQueries({ queryKey: ['agent-source-prefs'] });
      flash('Sources saved', 'ok');
    } catch (err) {
      flash(getAgentErrorMessage(err), 'err');
    } finally {
      setSaving(false);
    }
  };

  const effectiveSelected = selected ?? new Set<number>();

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ background: t.bgCard, border: `1px solid ${t.border}`, borderRadius: 16, padding: '24px' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 6 }}>Lead Sources</div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 20 }}>
          Choose which lead sources you want to monitor.
        </div>

        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: t.textMuted, fontSize: 13 }}>Loading…</div>
        ) : isError || sources.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: t.textMuted, fontSize: 13 }}>
            No lead sources configured yet. Ask your admin to add them.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
            {sources.map(source => {
              const isOn = effectiveSelected.has(source.id);
              return (
                <button
                  key={source.id}
                  type="button"
                  onClick={() => toggle(source.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
                    background: isOn ? t.accentBg : t.bgPage,
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
                    {source.description && (
                      <div style={{ fontSize: 12, color: t.textMuted, marginTop: 2 }}>{source.description}</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {msg && (
          <div style={{
            marginBottom: 16, padding: '9px 14px', borderRadius: 9, fontSize: 13,
            background: msgType === 'ok' ? t.greenBg : t.redBg,
            color: msgType === 'ok' ? t.green : t.red,
            border: `1px solid ${msgType === 'ok' ? t.green : t.red}30`,
          }}>{msg}</div>
        )}

        {sources.length > 0 && (
          <button onClick={handleSave} disabled={saving} style={{
            width: '100%', padding: '12px',
            background: saving ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
            cursor: saving ? 'not-allowed' : 'pointer',
            boxShadow: saving ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
          }}>
            {saving ? 'Saving…' : `Save (${effectiveSelected.size} selected)`}
          </button>
        )}
      </div>
    </div>
  );
};
