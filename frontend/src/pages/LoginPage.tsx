/**
 * Login Page — theme-aware, Apple-inspired
 */

import React, { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { getTokens } from '../utils/theme';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login, loading, error } = useAuth();
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch { /* handled by AuthContext */ }
  };

  return (
    <div style={{
      minHeight: '100vh', width: '100%',
      background: t.bgPage,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif',
      padding: '0 16px',
      transition: 'background 0.2s',
      position: 'relative',
    }}>
      {/* Ambient glow */}
      {theme === 'dark' && (
        <div style={{
          position: 'fixed', top: '15%', left: '50%', transform: 'translateX(-50%)',
          width: 700, height: 500, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(99,102,241,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      )}

      {/* Theme toggle top-right */}
      <button
        onClick={toggle}
        style={{
          position: 'fixed', top: 20, right: 20,
          background: t.bgCard, border: `1px solid ${t.border}`,
          borderRadius: 20, padding: '6px 14px',
          fontSize: 12, fontWeight: 500, color: t.textMuted,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <span>{theme === 'dark' ? '☀️' : '🌙'}</span>
        {theme === 'dark' ? 'Light mode' : 'Dark mode'}
      </button>

      <div style={{
        width: '100%', maxWidth: 380,
        background: t.bgCard,
        border: `1px solid ${t.border}`,
        borderRadius: 22,
        padding: '40px 36px',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        boxShadow: theme === 'dark'
          ? '0 24px 80px rgba(0,0,0,0.5)'
          : '0 8px 40px rgba(0,0,0,0.1)',
        transition: 'background 0.2s, border-color 0.2s',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 54, height: 54, borderRadius: 15,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 26, color: '#fff', fontWeight: 800, marginBottom: 16,
            boxShadow: '0 8px 24px rgba(99,102,241,0.4)',
          }}>L</div>
          <div style={{ fontSize: 21, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>LeadSync</div>
          <div style={{ fontSize: 13, color: t.textMuted, marginTop: 4 }}>Sign in to your account</div>
        </div>

        <form onSubmit={handleSubmit}>
          {(['username', 'password'] as const).map((field, i) => (
            <div key={field} style={{ marginBottom: i === 0 ? 14 : 20 }}>
              <label style={{
                display: 'block', fontSize: 11, fontWeight: 600,
                color: t.textFaint, marginBottom: 6,
                letterSpacing: '0.5px', textTransform: 'uppercase',
              }}>
                {field === 'username' ? 'Username' : 'Password'}
              </label>
              <input
                type={field === 'password' ? 'password' : 'text'}
                value={field === 'username' ? username : password}
                onChange={e => field === 'username' ? setUsername(e.target.value) : setPassword(e.target.value)}
                required
                disabled={loading}
                autoComplete={field === 'username' ? 'username' : 'current-password'}
                style={{
                  width: '100%', padding: '11px 14px',
                  background: t.bgInput,
                  border: `1.5px solid ${t.border}`,
                  borderRadius: 11, fontSize: 14, color: t.text,
                  outline: 'none', boxSizing: 'border-box',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
                onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                onBlur={e => (e.target.style.borderColor = t.border)}
              />
            </div>
          ))}

          {error && (
            <div style={{
              marginBottom: 16, padding: '10px 14px',
              background: t.redBg,
              border: `1px solid ${t.red}30`,
              borderRadius: 9, fontSize: 13, color: t.red,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '12px',
              background: loading ? t.accentBg : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: 11,
              fontSize: 14, fontWeight: 600, color: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 16px rgba(99,102,241,0.4)',
              transition: 'opacity 0.15s',
              letterSpacing: '-0.1px',
            }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};
