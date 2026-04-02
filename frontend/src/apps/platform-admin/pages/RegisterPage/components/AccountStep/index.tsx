import React from 'react';
import styles from '../../index.module.css';

interface AccountStepProps {
  username: string;
  password: string;
  confirmPassword: string;
  error: string;
  loading: boolean;
  tokens: Record<string, any>;
  isDark: boolean;
  onUsernameChange: (val: string) => void;
  onPasswordChange: (val: string) => void;
  onConfirmPasswordChange: (val: string) => void;
  onBack: () => void;
  onSubmit: (e: React.FormEvent) => void;
}

export const AccountStep: React.FC<AccountStepProps> = ({
  username, password, confirmPassword, error, loading, tokens: t, isDark,
  onUsernameChange, onPasswordChange, onConfirmPasswordChange, onBack, onSubmit,
}) => {
  const inputBg = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';

  return (
    <form onSubmit={onSubmit} className={styles.stepForm}>
      <div className={styles.stepTitle} style={{ color: t.text }}>Create your admin account</div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Username *</label>
        <input autoFocus value={username} onChange={e => onUsernameChange(e.target.value)} required
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Password *</label>
        <input type="password" value={password} onChange={e => onPasswordChange(e.target.value)} required
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Confirm Password *</label>
        <input type="password" value={confirmPassword} onChange={e => onConfirmPasswordChange(e.target.value)} required
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      {error && <div className={styles.errorAlert} style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }}>{error}</div>}
      <div className={styles.actionsRow}>
        <button type="button" onClick={onBack} className={styles.backButton} style={{ border: `1px solid ${t.border}`, color: t.textMuted }}>Back</button>
        <button type="submit" disabled={loading}
          className={`${styles.submitButton} ${loading ? styles.submitButtonLoading : styles.submitButtonActive}`}
          style={{ background: loading ? t.accentBg : undefined }}>
          {loading ? 'Creating account…' : 'Create Account'}
        </button>
      </div>
    </form>
  );
};
