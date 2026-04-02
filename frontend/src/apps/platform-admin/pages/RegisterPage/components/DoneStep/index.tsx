import React from 'react';
import styles from '../../index.module.css';

interface DoneStepProps {
  companyName: string;
  tokens: Record<string, any>;
  onSignIn: () => void;
}

export const DoneStep: React.FC<DoneStepProps> = ({ companyName, tokens: t, onSignIn }) => (
  <div className={styles.doneContainer}>
    <div className={styles.doneEmoji}>🎉</div>
    <div className={styles.doneTitle} style={{ color: t.text }}>
      Welcome to LeadSync, {companyName}!
    </div>
    <div className={styles.doneMessage} style={{ color: t.textMuted }}>
      Your account is ready. Sign in to start configuring your pipeline, templates, and lead sources.
    </div>
    <button onClick={onSignIn} className={styles.doneButton}>Sign In →</button>
  </div>
);
