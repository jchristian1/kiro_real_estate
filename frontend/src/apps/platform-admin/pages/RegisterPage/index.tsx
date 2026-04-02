/**
 * RegisterPage — company self-service signup.
 * Creates a company + admin user in one step, then redirects to login.
 */
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import { CompanyStep, AccountStep, DoneStep } from './components';
import styles from './index.module.css';

type Step = 'company' | 'account' | 'done';
const STEPS = ['company', 'account'];

export const RegisterPage: React.FC = () => {
  const { theme, toggle } = useTheme();
  const t = getTokens(theme);
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  const [step, setStep] = useState<Step>('company');
  const [companyName, setCompanyName] = useState('');
  const [companyEmail, setCompanyEmail] = useState('');
  const [companyPhone, setCompanyPhone] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
      const res = await fetch(`${API_BASE_URL}/auth/register`, {
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

  const stepIdx = STEPS.indexOf(step);

  return (
    <div className={styles.page} style={{ background: t.bgPage }}>
      {isDark && <div className={styles.glowOrb} />}

      <button onClick={toggle} className={styles.themeToggle}
        style={{ background: t.bgCard, border: `1px solid ${t.border}`, color: t.textMuted }}>
        <span>{isDark ? '☀️' : '🌙'}</span>
        {isDark ? 'Light' : 'Dark'}
      </button>

      <div className={`${styles.card} ${isDark ? styles.cardShadowDark : styles.cardShadowLight}`}
        style={{ background: t.bgCard, border: `1px solid ${t.border}` }}>

        <div className={styles.logoContainer}>
          <div className={styles.logoIcon}>L</div>
          <div className={styles.logoTitle} style={{ color: t.text }}>LeadSync</div>
          <div className={styles.logoSubtitle} style={{ color: t.textMuted }}>
            {step === 'done' ? "You're all set" : 'Create your company account'}
          </div>
        </div>

        {step !== 'done' && (
          <div className={styles.progressBar}>
            {STEPS.map((s, i) => (
              <div key={s} className={styles.progressSegment}
                style={{ background: i <= stepIdx ? '#6366f1' : t.border }} />
            ))}
          </div>
        )}

        {step === 'company' && (
          <CompanyStep
            companyName={companyName} companyEmail={companyEmail} companyPhone={companyPhone}
            error={error} tokens={t} isDark={isDark}
            onCompanyNameChange={setCompanyName} onCompanyEmailChange={setCompanyEmail}
            onCompanyPhoneChange={setCompanyPhone} onNext={handleCompanyNext} />
        )}

        {step === 'account' && (
          <AccountStep
            username={username} password={password} confirmPassword={confirmPassword}
            error={error} loading={loading} tokens={t} isDark={isDark}
            onUsernameChange={setUsername} onPasswordChange={setPassword}
            onConfirmPasswordChange={setConfirmPassword}
            onBack={() => { setStep('company'); setError(''); }} onSubmit={handleSubmit} />
        )}

        {step === 'done' && (
          <DoneStep companyName={companyName} tokens={t} onSignIn={() => navigate('/login')} />
        )}

        {step !== 'done' && (
          <div className={styles.signInLink} style={{ color: t.textFaint }}>
            Already have an account?{' '}
            <Link to="/login" className={styles.signInAnchor} style={{ color: t.accent }}>Sign in</Link>
          </div>
        )}
      </div>
    </div>
  );
};
