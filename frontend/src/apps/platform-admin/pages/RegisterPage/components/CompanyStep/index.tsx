import React from 'react';
import styles from '../../index.module.css';

interface CompanyStepProps {
  companyName: string;
  companyEmail: string;
  companyPhone: string;
  error: string;
  tokens: Record<string, any>;
  isDark: boolean;
  onCompanyNameChange: (val: string) => void;
  onCompanyEmailChange: (val: string) => void;
  onCompanyPhoneChange: (val: string) => void;
  onNext: (e: React.FormEvent) => void;
}

export const CompanyStep: React.FC<CompanyStepProps> = ({
  companyName, companyEmail, companyPhone, error, tokens: t, isDark,
  onCompanyNameChange, onCompanyEmailChange, onCompanyPhoneChange, onNext,
}) => {
  const inputBg = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';

  return (
    <form onSubmit={onNext} className={styles.stepForm}>
      <div className={styles.stepTitle} style={{ color: t.text }}>About your company</div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Company Name *</label>
        <input autoFocus value={companyName} onChange={e => onCompanyNameChange(e.target.value)} required
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Business Email</label>
        <input type="email" value={companyEmail} onChange={e => onCompanyEmailChange(e.target.value)} placeholder="optional"
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      <div>
        <label className={styles.label} style={{ color: t.textFaint }}>Phone</label>
        <input type="tel" value={companyPhone} onChange={e => onCompanyPhoneChange(e.target.value)} placeholder="optional"
          className={styles.input} style={{ background: inputBg, border: `1.5px solid ${t.border}`, color: t.text }}
          onFocus={e => (e.target.style.borderColor = t.borderFocus)} onBlur={e => (e.target.style.borderColor = t.border)} />
      </div>
      {error && <div className={styles.errorAlert} style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }}>{error}</div>}
      <button type="submit" className={styles.primaryButton}>Continue →</button>
    </form>
  );
};
