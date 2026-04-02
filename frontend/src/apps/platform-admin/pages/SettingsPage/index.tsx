/**
 * Settings Page — theme-aware, with appearance section
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

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

  return (
    <div className={styles.loadingContainer} style={{ color: t.textFaint }}>
      Loading settings…
    </div>
  );

  if (fetchError) return (
    <div className={styles.errorContainer} style={{ color: t.red }}>
      {fetchError}
    </div>
  );

  if (!draft) return null;
  const isDirty = JSON.stringify(draft) !== JSON.stringify(settings);

  return (
    <div className={styles.container}>

      {/* ── Appearance ── */}
      <div className={styles.card} style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>
        <div className={styles.sectionTitle} style={{ color: t.textMuted }}>Appearance</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div className={styles.fieldLabel} style={{ color: t.text }}>Theme</div>
            <div className={styles.fieldDescription} style={{ color: t.textMuted }}>Choose between dark and light interface</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['dark', 'light'] as const).map(opt => (
              <button
                key={opt}
                onClick={() => setTheme(opt)}
                className={styles.themeButton}
                style={{
                  borderRadius: 10,
                  border: `1.5px solid ${theme === opt ? t.accent : t.border}`,
                  background: theme === opt ? t.accentBg : t.bgCard,
                  color: theme === opt ? t.accent : t.textMuted,
                  fontWeight: theme === opt ? 600 : 400,
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
      <div className={styles.card} style={{ background: t.bgCard, border: `1px solid ${t.border}` }} data-testid="settings-form">
        <div className={styles.sectionTitle} style={{ color: t.textMuted }}>System</div>

        {FIELDS.map((f, i) => (
          <div key={f.key} className={`${styles.fieldRow} ${i === FIELDS.length - 1 ? styles.fieldRowLast : ''}`} style={{ borderBottom: i === FIELDS.length - 1 ? 'none' : `1px solid ${t.border}` }}>
            <div style={{ flex: 1 }}>
              <div className={styles.fieldLabel} style={{ color: t.text }}>{f.label}</div>
              <div className={styles.fieldDescription} style={{ color: t.textMuted }}>{f.description}</div>
              {validationErrors[f.key] && (
                <div className={styles.fieldError} style={{ color: t.red }} role="alert" data-testid={`error-${f.key}`}>
                  {validationErrors[f.key]}
                </div>
              )}
            </div>
            <div className={styles.fieldInputContainer}>
              {f.type === 'boolean' ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft[f.key] as boolean}
                  onClick={() => handleChange(f.key, !(draft[f.key] as boolean))}
                  data-testid={`toggle-${f.key}`}
                  className={styles.toggleButton}
                  style={{
                    background: draft[f.key] ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.border,
                  }}
                >
                  <span className={styles.toggleThumb} style={{
                    left: draft[f.key] ? 21 : 3,
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
                  className={styles.numberInput}
                  style={{
                    background: t.bgInput,
                    border: `1.5px solid ${validationErrors[f.key] ? t.red : t.border}`,
                    color: t.text,
                  }}
                  onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                  onBlur={e => (e.target.style.borderColor = validationErrors[f.key] ? t.red : t.border)}
                />
              )}
            </div>
          </div>
        ))}

        <div className={styles.formActions} style={{ borderTop: `1px solid ${t.border}` }}>
          <button
            onClick={handleReset}
            disabled={!isDirty || saving}
            data-testid="reset-btn"
            className={styles.resetButton}
            style={{
              background: t.bgCard, border: `1px solid ${t.border}`,
              color: t.textMuted,
              cursor: isDirty ? 'pointer' : 'not-allowed',
              opacity: isDirty ? 1 : 0.4,
            }}
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || saving || Object.keys(validationErrors).length > 0}
            data-testid="save-btn"
            className={styles.saveButton}
            style={{
              background: isDirty && !saving ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : t.accentBg,
              cursor: isDirty && !saving ? 'pointer' : 'not-allowed',
              opacity: isDirty && !saving ? 1 : 0.5,
              boxShadow: isDirty ? '0 4px 14px rgba(99,102,241,0.35)' : 'none',
            }}
          >
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
