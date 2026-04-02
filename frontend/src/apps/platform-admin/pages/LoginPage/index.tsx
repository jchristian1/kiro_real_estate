/**
 * Login Page — theme-aware, Apple-inspired
 */
import React, { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/apps/platform-admin/contexts/AuthContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import styles from './index.module.css';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login, loading, error } = useAuth();
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch { /* handled by AuthContext */ }
  };

  return (
    <div className={styles.page} style={{ background: t.bgPage }}>
      {isDark && <div className={styles.glowOrb} />}

      <button onClick={toggle} className={styles.themeToggle}
        style={{ background: t.bgCard, border: `1px solid ${t.border}`, color: t.textMuted }}>
        <span>{isDark ? '☀️' : '🌙'}</span>
        {isDark ? 'Light mode' : 'Dark mode'}
      </button>

      <div className={`${styles.card} ${isDark ? styles.cardShadowDark : styles.cardShadowLight}`}
        style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>

        <div className={styles.logoContainer}>
          <div className={styles.logoIcon}>L</div>
          <div className={styles.logoTitle} style={{ color: t.text }}>LeadSync</div>
          <div className={styles.logoSubtitle} style={{ color: t.textMuted }}>Sign in to your account</div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className={styles.fieldUsername}>
            <label className={styles.label} style={{ color: t.textFaint }}>Username</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)}
              required disabled={loading} autoComplete="username"
              className={styles.input}
              style={{ background: t.bgInput, border: `1.5px solid ${t.border}`, color: t.text }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)}
              onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>

          <div className={styles.fieldPassword}>
            <label className={styles.label} style={{ color: t.textFaint }}>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              required disabled={loading} autoComplete="current-password"
              className={styles.input}
              style={{ background: t.bgInput, border: `1.5px solid ${t.border}`, color: t.text }}
              onFocus={e => (e.target.style.borderColor = t.borderFocus)}
              onBlur={e => (e.target.style.borderColor = t.border)} />
          </div>

          {error && (
            <div className={styles.errorAlert}
              style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading}
            className={`${styles.submitButton} ${loading ? styles.submitButtonLoading : styles.submitButtonActive}`}
            style={{ background: loading ? t.accentBg : undefined }}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className={styles.signUpLink} style={{ color: t.textFaint }}>
          New company?{' '}
          <Link to="/register" className={styles.signUpAnchor} style={{ color: t.accent }}>
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
};
