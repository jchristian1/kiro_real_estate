/**
 * Settings Page — theme-aware, with appearance section
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '../../../shared/contexts/ToastContext';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface Settings {
  sync_interval_seconds: number;
  regex_timeout_ms: number;
  session_timeout_hours: number;
  max_leads_per_page: number;
  enable_auto_restart: boolean;
}

interface FieldConfig {
  key: keyof Settings;
  label: string;
  description: string;
  type: 'number' | 'boolean';
  min?: number;
  max?: number;
}

const FIELDS: FieldConfig[] = [
  { key: 'sync_interval_seconds', label: 'Sync Interval (seconds)', description: 'How often watchers check for new emails (60–3600)', type: 'number', min: 60, max: 3600 },
  { key: 'regex_timeout_ms', label: 'Regex Timeout (ms)', description: 'Maximum time for regex execution (100–5000)', type: 'number', min: 100, max: 5000 },
  { key: 'session_timeout_hours', label: 'Session Timeout (hours)', description: 'How long sessions remain valid (1–168)', type: 'number', min: 1, max: 168 },
  { key: 'max_leads_per_page', label: 'Max Leads Per Page', description: 'Maximum leads shown per page (10–1000)', type: 'number', min: 10, max: 1000 },
  { key: 'enable_auto_restart', label: 'Auto-Restart Watchers', description: 'Automatically restart failed watchers', type: 'boolean' },
];

export const SettingsPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const { theme, setTheme } = useTheme();
  const t = getTokens(theme);

  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Partial<Record<keyof Settings, string>>>({});

  useEffect(() => {
    axios.get<Settings>(`${API_BASE_URL}/settings`)
      .then(r => { setSettings(r.data); setDraft(r.data); })
      .catch(() => setFetchError('Failed to load settings'))
      .finally(() => setLoading(false));
  }, []);

  const validate = (d: Settings) => {
    const errs: Partial<Record<keyof Settings, string>> = {};
    FIELDS.forEach(f => {
      if (f.type === 'number' && f.min !== undefined && f.max !== undefined) {
        const v = d[f.key] as number;
        if (v < f.min || v > f.max) errs[f.key] = `Must be between ${f.min} and ${f.max}`;
      }
    });
    return errs;
  };

  const handleChange = (key: keyof Settings, val: string | boolean) => {
    if (!draft) return;
    const updated = { ...draft, [key]: typeof val === 'boolean' ? val : Number(val) };
    setDraft(updated);
    setValidationErrors(validate(updated));
  };

  const handleSave = async () => {
    if (!draft) return;
    const errs = validate(draft);
    if (Object.keys(errs).length > 0) { setValidationErrors(errs); return; }
    setSaving(true);
    try {
      const res = await axios.put<Settings>(`${API_BASE_URL}/settings`, draft);
      setSettings(res.data); setDraft(res.data);
      success('Settings saved');
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      toastError(e.response?.data?.detail || e.response?.data?.message || 'Failed to save settings');
    } finally { setSaving(false); }
  };

  const handleReset = () => { if (settings) { setDraft(settings); setValidationErrors({}); } };

  const card: React.CSSProperties = {
    background: t.bgCard,
    border: `1px solid ${t.border}`,
    borderRadius: 16,
    padding: '24px',
    marginBottom: 20,
    transition: 'background 0.2s',
  };

  const sectionTitle: React.CSSProperties = {
    fontSize: 13, fontWeight: 600, color: t.textMuted,
    textTransform: 'uppercase', letterSpacing: '0.5px',
    marginBottom: 18,
  };

  const fieldRow: React.CSSProperties = {
    display: 'flex', alignItems: 'flex-start',
    justifyContent: 'space-between', gap: 24,
    paddingBottom: 18, marginBottom: 18,
    borderBottom: `1px solid ${t.border}`,
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.textFaint, fontSize: 14 }}>
      Loading settings…
    </div>
  );

  if (fetchError) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: t.red, fontSize: 14 }}>
      {fetchError}
    </div>
  );

  if (!draft) return null;
  const isDirty = JSON.stringify(draft) !== JSON.stringify(settings);

  return (
    <div style={{ maxWidth: 680 }}>

      {/* ── Appearance ── */}
      <div style={card}>
        <div style={sectionTitle}>Appearance</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: t.text, marginBottom: 3 }}>Theme</div>
            <div style={{ fontSize: 12, color: t.textMuted }}>Choose between dark and light interface</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['dark', 'light'] as const).map(opt => (
              <button
                key={opt}
                onClick={() => setTheme(opt)}
                style={{
                  padding: '7px 18px',
                  borderRadius: 10,
                  border: `1.5px solid ${theme === opt ? t.accent : t.border}`,
                  background: theme === opt ? t.accentBg : t.bgCard,
                  color: theme === opt ? t.accent : t.textMuted,
                  fontSize: 13, fontWeight: theme === opt ? 600 : 400,
                  cursor: 'pointer', transition: 'all 0.15s',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <span>{opt === 'dark' ? '🌙' : '☀️'}</span>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── System Settings ── */}
      <div style={card} data-testid="settings-form">
        <div style={sectionTitle}>System</div>

        {FIELDS.map((f, i) => (
          <div key={f.key} style={{ ...fieldRow, ...(i === FIELDS.length - 1 ? { borderBottom: 'none', marginBottom: 0, paddingBottom: 0 } : {}) }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: t.text, marginBottom: 2 }}>{f.label}</div>
              <div style={{ fontSize: 12, color: t.textMuted }}>{f.description}</div>
              {validationErrors[f.key] && (
                <div style={{ fontSize: 12, color: t.red, marginTop: 4 }} role="alert" data-testid={`error-${f.key}`}>
                  {validationErrors[f.key]}
                </div>
              )}
            </div>
            <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
              {f.type === 'boolean' ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft[f.key] as boolean}
                  onClick={() => handleChange(f.key, !(draft[f.key] as boolean))}
                  data-testid={`toggle-${f.key}`}
                  style={{
                    position: 'relative', width: 44, height: 26,
                    borderRadius: 13, border: 'none', cursor: 'pointer',
                    background: draft[f.key] ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.border,
                    transition: 'background 0.2s',
                    padding: 0,
                  }}
                >
                  <span style={{
                    position: 'absolute', top: 3,
                    left: draft[f.key] ? 21 : 3,
                    width: 20, height: 20, borderRadius: '50%',
                    background: '#fff',
                    transition: 'left 0.2s',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
                  }} />
                </button>
              ) : (
                <input
                  id={f.key}
                  type="number"
                  value={draft[f.key] as number}
                  min={f.min}
                  max={f.max}
                  onChange={e => handleChange(f.key, e.target.value)}
                  data-testid={`input-${f.key}`}
                  style={{
                    width: 110, padding: '8px 12px',
                    background: t.bgInput,
                    border: `1.5px solid ${validationErrors[f.key] ? t.red : t.border}`,
                    borderRadius: 9, fontSize: 13, color: t.text,
                    outline: 'none', textAlign: 'right',
                    transition: 'border-color 0.15s',
                  }}
                  onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                  onBlur={e => (e.target.style.borderColor = validationErrors[f.key] ? t.red : t.border)}
                />
              )}
            </div>
          </div>
        ))}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20, paddingTop: 18, borderTop: `1px solid ${t.border}` }}>
          <button
            onClick={handleReset}
            disabled={!isDirty || saving}
            data-testid="reset-btn"
            style={{
              padding: '8px 18px',
              background: t.bgCard, border: `1px solid ${t.border}`,
              borderRadius: 9, fontSize: 13, fontWeight: 500,
              color: t.textMuted, cursor: isDirty ? 'pointer' : 'not-allowed',
              opacity: isDirty ? 1 : 0.4, transition: 'all 0.15s',
            }}
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || saving || Object.keys(validationErrors).length > 0}
            data-testid="save-btn"
            style={{
              padding: '8px 20px',
              background: isDirty && !saving ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.accentBg,
              border: 'none', borderRadius: 9,
              fontSize: 13, fontWeight: 600, color: '#fff',
              cursor: isDirty && !saving ? 'pointer' : 'not-allowed',
              opacity: isDirty && !saving ? 1 : 0.5,
              boxShadow: isDirty ? '0 4px 14px rgba(99,102,241,0.35)' : 'none',
              transition: 'all 0.15s',
            }}
          >
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
