/**
 * Settings Page Component
 * Requirements: 18.1, 18.2, 18.3
 */
import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '../contexts/ToastContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Partial<Record<keyof Settings, string>>>({});

  useEffect(() => {
    axios.get<Settings>(`${API_BASE_URL}/settings`)
      .then((r) => { setSettings(r.data); setDraft(r.data); })
      .catch(() => setFetchError('Failed to load settings'))
      .finally(() => setLoading(false));
  }, []);

  const validate = (d: Settings): Partial<Record<keyof Settings, string>> => {
    const errs: Partial<Record<keyof Settings, string>> = {};
    FIELDS.forEach((f) => {
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
    const errs = validate(updated);
    setValidationErrors(errs);
  };

  const handleSave = async () => {
    if (!draft) return;
    const errs = validate(draft);
    if (Object.keys(errs).length > 0) { setValidationErrors(errs); return; }
    setSaving(true);
    try {
      const res = await axios.put<Settings>(`${API_BASE_URL}/settings`, draft);
      setSettings(res.data);
      setDraft(res.data);
      success('Settings saved successfully');
    } catch (err) {
      const e = err as AxiosError<{ detail?: string; message?: string }>;
      toastError(e.response?.data?.detail || e.response?.data?.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => { if (settings) { setDraft(settings); setValidationErrors({}); } };

  if (loading) return <div className="flex items-center justify-center h-64"><span className="text-gray-500">Loading settings...</span></div>;
  if (fetchError) return <div className="flex items-center justify-center h-64"><span className="text-red-600">{fetchError}</span></div>;
  if (!draft) return null;

  const isDirty = JSON.stringify(draft) !== JSON.stringify(settings);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Settings</h1>

      <div className="bg-white rounded-lg shadow p-6 space-y-6" data-testid="settings-form">
        {FIELDS.map((f) => (
          <div key={f.key} className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <label htmlFor={f.key} className="block text-sm font-medium text-gray-900">{f.label}</label>
              <p className="text-xs text-gray-500 mt-0.5">{f.description}</p>
              {validationErrors[f.key] && (
                <p className="text-xs text-red-600 mt-1" role="alert" data-testid={`error-${f.key}`}>{validationErrors[f.key]}</p>
              )}
            </div>
            <div className="flex-shrink-0">
              {f.type === 'boolean' ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft[f.key] as boolean}
                  onClick={() => handleChange(f.key, !(draft[f.key] as boolean))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${draft[f.key] ? 'bg-blue-600' : 'bg-gray-200'}`}
                  data-testid={`toggle-${f.key}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${draft[f.key] ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              ) : (
                <input
                  id={f.key}
                  type="number"
                  value={draft[f.key] as number}
                  min={f.min}
                  max={f.max}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  className={`w-32 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${validationErrors[f.key] ? 'border-red-500' : 'border-gray-300'}`}
                  data-testid={`input-${f.key}`}
                />
              )}
            </div>
          </div>
        ))}

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button onClick={handleReset} disabled={!isDirty || saving}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            data-testid="reset-btn">
            Reset
          </button>
          <button onClick={handleSave} disabled={!isDirty || saving || Object.keys(validationErrors).length > 0}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            data-testid="save-btn">
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};
