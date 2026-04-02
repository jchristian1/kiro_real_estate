import React from 'react';
import styles from '../../index.module.css';

interface Option { value: string; label: string; }

interface FormQuestionProps {
  index: number;
  questionKey: string;
  type: string;
  label: string;
  required: boolean;
  options?: Option[];
  value: string | string[] | undefined;
  onChange: (key: string, value: string, multi?: boolean) => void;
}

export const FormQuestion: React.FC<FormQuestionProps> = ({
  index, questionKey, type, label, required, options, value, onChange,
}) => (
  <div className={styles.questionBlock}>
    <label className={styles.questionLabel}>
      {index + 1}. {label}
      {required && <span className={styles.requiredMark}>*</span>}
    </label>

    {type === 'single_choice' && options && (
      <div className={styles.optionsList}>
        {options.map(opt => (
          <label key={opt.value}
            className={`${styles.optionLabel} ${value === opt.value ? styles.optionLabelSelected : styles.optionLabelDefault}`}>
            <input type="radio" name={questionKey} value={opt.value}
              checked={value === opt.value}
              onChange={() => onChange(questionKey, opt.value)}
              style={{ accentColor: '#007AFF' }} />
            <span className={styles.optionText}>{opt.label}</span>
          </label>
        ))}
      </div>
    )}

    {type === 'multi_select' && options && (
      <div className={styles.optionsList}>
        {options.map(opt => {
          const selected = ((value as string[]) || []).includes(opt.value);
          return (
            <label key={opt.value}
              className={`${styles.optionLabel} ${selected ? styles.optionLabelSelected : styles.optionLabelDefault}`}>
              <input type="checkbox" value={opt.value} checked={selected}
                onChange={() => onChange(questionKey, opt.value, true)}
                style={{ accentColor: '#007AFF' }} />
              <span className={styles.optionText}>{opt.label}</span>
            </label>
          );
        })}
      </div>
    )}

    {type === 'free_text' && (
      <textarea value={(value as string) || ''} rows={3}
        onChange={e => onChange(questionKey, e.target.value)}
        className={styles.input} placeholder="Your answer…" />
    )}

    {(type === 'phone' || type === 'email') && (
      <input type={type === 'email' ? 'email' : 'tel'}
        value={(value as string) || ''}
        onChange={e => onChange(questionKey, e.target.value)}
        className={styles.input}
        placeholder={type === 'email' ? 'your@email.com' : '+1 (555) 000-0000'} />
    )}
  </div>
);
