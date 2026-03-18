/**
 * RegisterPage — company self-service signup.
 * Creates a company + admin user in one step, then redirects to login.
 */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

type Step = 'company' | 'account' | 'done';

export const RegisterPage: React.FC = () => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>('company');
  const [companyName, setCompanyName] = useState('');
  const [companyEmail, setCompanyEmail] = useState('');
  const [companyPhone, setCompanyPhone] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isDark = theme === 'dark';

  const inp: React.CSSProperties = {
    width: '100%', padding: '11px 14px',
    background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    border: `1.5px solid ${t.border}`,
    borderRadius: 11, fontSize: 14, color: t.text,
    outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.15s',
  };

  const label: React.CSSProperties = {
    display: 'block', fontSize: 11, fontWeight: 600,
    color: t.textFaint, marginBottom: 6,
    letterSpacing: '0.5px', textTransform: 'uppercase',
  };

  const handleCompanyNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim()) { setError('Company name is required.'); return; }
    setError('');
    setStep('account');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) { setError('Passwords do not match.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    setError(''); setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName,
          company_email: companyEmail || undefined,
          company_phone: companyPhone || undefined,
          admin_username: username,
          admin_password: password,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Registration failed.');
      }
      setStep('done');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const STEPS = ['company', 'account'];
  const stepIdx = STEPS.indexOf(step);

  return (
    <div style={{
      minHeight: '100vh', background: t.bgPage,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
      padding: '0 16px', transition: 'background 0.2s', position: 'relative',
    }}>
      {isDark && (
        <div style={{
          position: 'fixed', top: '10%', left: '50%', transform: 'translateX(-50%)',
          width: 700, height: 500, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(99,102,241,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      )}

      <button onClick={toggle} style={{
        position: 'fixed', top: 20, right: 20,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 20, padding: '6px 14px',
        fontSize: 12, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span>{isDark ? '☀️' : '🌙'}</span>
        {isDark ? 'Light' : 'Dark'}
      </button>

      <div style={{
        width: '100%', maxWidth: 420,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 22, padding: '40px 36px',
        boxShadow: isDark ? '0 24px 80px rgba(0,0,0,0.5)' : '0 8px 40px rgba(0,0,0,0.1)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            width: 54, height: 54, borderRadius: 15,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 26, color: '#fff', fontWeight: 800, marginBottom: 14,
            boxShadow: '0 8px 24px rgba(99,102,241,0.4)',
          }}>L</div>
          <div style={{ fontSize: 21, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>LeadSync</div>
          <div style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>
            {step === 'done' ? 'You\'re all set' : 'Create your company account'}
          </div>
        </div>

        {/* Progress dots */}
        {step !== 'done' && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 28 }}>
            {STEPS.map((s, i) => (
              <div key={s} style={{
                flex: 1, height: 3, borderRadius: 2,
                background: i <= stepIdx ? '#6366f1' : t.border,
                transition: 'background 0.2s',
              }} />
            ))}
          </div>
        )}

        {/* ── Step 1: Company info ── */}
        {step === 'company' && (
          <form onSubmit={handleCompanyNext} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 4 }}>About your company</div>
            <div>
              <label style={label}>Company Name *</label>
              <input autoFocus value={companyName} onChange={e => setCompanyName(e.target.value)} required style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            <div>
              <label style={label}>Business Email</label>
              <input type="email" value={companyEmail} onChange={e => setCompanyEmail(e.target.value)} placeholder="optional" style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            <div>
              <label style={label}>Phone</label>
              <input type="tel" value={companyPhone} onChange={e => setCompanyPhone(e.target.value)} placeholder="optional" style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            {error && <div style={{ padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>{error}</div>}
            <button type="submit" style={{
              padding: '12px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
              cursor: 'pointer', boxShadow: '0 4px 16px rgba(99,102,241,0.4)', marginTop: 4,
            }}>Continue →</button>
          </form>
        )}

        {/* ── Step 2: Admin account ── */}
        {step === 'account' && (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: t.text, marginBottom: 4 }}>Create your admin account</div>
            <div>
              <label style={label}>Username *</label>
              <input autoFocus value={username} onChange={e => setUsername(e.target.value)} required style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            <div>
              <label style={label}>Password *</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            <div>
              <label style={label}>Confirm Password *</label>
              <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required style={inp}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
            </div>
            {error && <div style={{ padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <button type="button" onClick={() => { setStep('company'); setError(''); }} style={{
                flex: 1, padding: '12px', background: 'none', border: `1px solid ${t.border}`,
                borderRadius: 11, fontSize: 14, fontWeight: 500, color: t.textMuted, cursor: 'pointer',
              }}>Back</button>
              <button type="submit" disabled={loading} style={{
                flex: 2, padding: '12px',
                background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
              }}>{loading ? 'Creating account…' : 'Create Account'}</button>
            </div>
          </form>
        )}

        {/* ── Done ── */}
        {step === 'done' && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🎉</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: t.text, marginBottom: 8 }}>
              Welcome to LeadSync, {companyName}!
            </div>
            <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 28, lineHeight: 1.6 }}>
              Your account is ready. Sign in to start configuring your pipeline, templates, and lead sources.
            </div>
            <button onClick={() => navigate('/login')} style={{
              width: '100%', padding: '12px',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
              cursor: 'pointer', boxShadow: '0 4px 16px rgba(99,102,241,0.4)',
            }}>Sign In →</button>
          </div>
        )}

        {/* Sign in link */}
        {step !== 'done' && (
          <div style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: t.textFaint }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: t.accent, textDecoration: 'none', fontWeight: 500 }}>Sign in</Link>
          </div>
        )}
      </div>
    </div>
  );
};
