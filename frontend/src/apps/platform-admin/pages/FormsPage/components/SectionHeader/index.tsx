import React from 'react';
import styles from '../../index.module.css';

interface SectionHeaderProps {
  icon: string;
  label: string;
  divider: string;
  textFaint: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({ icon, label, divider, textFaint }) => (
  <div className={styles.sectionHeader}>
    <span className={styles.sectionIcon}>{icon}</span>
    <span className={styles.sectionLabel} style={{ color: textFaint }}>{label}</span>
    <div className={styles.sectionDivider} style={{ background: divider }} />
  </div>
);
