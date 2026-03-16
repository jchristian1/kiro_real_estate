/**
 * Agent Login Page — matches admin LoginPage style exactly.
 */

import React, { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAgentAuth } from '../contexts/AgentAuthContext';
import { useTheme } from '../../../shared/contexts/ThemeContext';
import { getTokens } from '../../../shared/utils/theme';
import { getAgentErrorMessage } from '../api/agentApi';

export const AgentLoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAgentAuth();
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/agent/dashboard');
    } catch (err) {
      setError(getAgentErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', width: '100%', background: t.bgPage,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif',
      padding: '0 16px', transition: 'background 0.2s', position: 'relative',
    }}>
      {theme === 'dark' && (
        <div style={{
          position: 'fixed', top: '15%', left: '50%', transform: 'translateX(-50%)',
          width: 700, height: 500, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(99,102,241,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      )}
      <button onClick={toggle} style={{
        position: 'fixed', top: 20, right: 20,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 20, padding: '6px 14px',
        fontSize: 12, fontWeight: 500, color: t.textMuted,
        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span>{theme === 'dark' ? '☀️' : '🌙'}</span>
        {theme === 'dark' ? 'Light mode' : 'Dark mode'}
      </button>

      <div style={{
        width: '100%', maxWidth: 380,
        background: t.bgCard, border: `1px solid ${t.border}`,
        borderRadius: 22, padding: '40px 36px',
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        boxShadow: theme === 'dark' ? '0 24px 80px rgba(0,0,0,0.5)' : '0 8px 40px rgba(0,0,0,0.1)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 54, height: 54, borderRadius: 15,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 26, color: '#fff', fontWeight: 800, marginBottom: 16,
            boxShadow: '0 8px 24px rgba(99,102,241,0.4)',
          }}>L</div>
          <div style={{ fontSize: 21, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>Agent Portal</div>
          <div style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>Sign in to your account</div>
        </div>

        <form onSubmit={handleSubmit}>
          {[
            { field: 'email', label: 'Email', type: 'email', value: email, set: setEmail },
            { field: 'password', label: 'Password', type: 'password', value: password, set: setPassword },
          ].map(({ field, label, type, value, set }) => (
            <div key={field} style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: t.textFaint, marginBottom: 6, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                {label}
              </label>
              <input
                type={type} value={value} onChange={e => set(e.target.value)}
                required disabled={loading} autoComplete={field}
                style={{
                  width: '100%', padding: '11px 14px',
                  background: t.bgInput, border: `1.5px solid ${t.border}`,
                  borderRadius: 11, fontSize: 14, color: t.text,
                  outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.15s',
                }}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)}
              />
            </div>
          ))}

          {error && (
            <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: '100%', padding: '12px', marginTop: 6,
            background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', borderRadius: 11, fontSize: 14, fontWeight: 600, color: '#fff',
            cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
            transition: 'opacity 0.15s',
          }}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: t.textMuted }}>
          Don't have an account?{' '}
          <Link to="/agent/signup" style={{ color: t.accent, textDecoration: 'none', fontWeight: 500 }}>
            Sign up
          </Link>
        </div>
      </div>
    </div>
  );
};
