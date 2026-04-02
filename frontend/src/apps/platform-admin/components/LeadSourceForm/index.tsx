import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useT } from '@/shared/hooks';
import { leadSourceSchema } from '@/shared/utils';
import { Template, LeadSourceFormValues } from '@/models';
import styles from './index.module.css';

export interface LeadSourceFormProps {
  initialValues?: Partial<LeadSourceFormValues>;
  isEditMode?: boolean;
  onSubmit: (data: LeadSourceFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
  serverError?: string | null;
  templates?: Template[];
}

export const LeadSourceForm: React.FC<LeadSourceFormProps> = ({
  initialValues, isEditMode = false, onSubmit, onCancel, isSubmitting = false, serverError, templates = [],
}) => {
  const t = useT();
  const { register, handleSubmit, formState: { errors } } = useForm<LeadSourceFormValues>({
    resolver: zodResolver(leadSourceSchema),
    defaultValues: {
      sender_email: initialValues?.sender_email ?? '',
      identifier_snippet: initialValues?.identifier_snippet ?? '',
      name_regex: initialValues?.name_regex ?? '',
      phone_regex: initialValues?.phone_regex ?? '',
      template_id: initialValues?.template_id ?? null,
      auto_respond_enabled: initialValues?.auto_respond_enabled ?? false,
    },
  });

  const fieldStyle = (hasError: boolean): React.CSSProperties => ({
    ...t.input,
    borderColor: hasError ? t.red : t.border,
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Lead source form">
      {serverError && (
        <div className={styles.serverError} style={{ background: t.redBg, border: `1px solid ${t.red}40`, color: t.red }} role="alert">{serverError}</div>
      )}

      {[
        { id: 'sender_email', label: 'Sender Email', type: 'email', placeholder: 'leads@zillow.com', error: errors.sender_email?.message, mono: false },
        { id: 'identifier_snippet', label: 'Identifier Snippet', type: 'text', placeholder: 'e.g. New Lead Notification', error: errors.identifier_snippet?.message, mono: false },
        { id: 'name_regex', label: 'Name Regex', type: 'text', placeholder: 'e.g. Name:\\s*(.+)', error: errors.name_regex?.message, mono: true },
        { id: 'phone_regex', label: 'Phone Regex', type: 'text', placeholder: 'e.g. Phone:\\s*([\\d\\-\\(\\)\\s]+)', error: errors.phone_regex?.message, mono: true },
      ].map(({ id, label, type, placeholder, error, mono }) => (
        <div key={id} className={styles.fieldGroup}>
          <label htmlFor={id} style={t.labelStyle}>{label} <span style={{ color: t.red }}>*</span></label>
          <input id={id} type={type} {...register(id as keyof LeadSourceFormValues)} disabled={isSubmitting}
            placeholder={placeholder} style={{ ...fieldStyle(!!error), fontFamily: mono ? 'monospace' : 'inherit' }} />
          {error && <p className={styles.fieldError} style={{ color: t.red }} role="alert">{error}</p>}
        </div>
      ))}

      <div className={styles.fieldGroup}>
        <label htmlFor="template_id" style={t.labelStyle}>Response Template</label>
        <select id="template_id" disabled={isSubmitting} style={fieldStyle(!!errors.template_id)}
          {...register('template_id', { setValueAs: (v) => (v === '' || v === null ? null : Number(v)) })}>
          <option value="">— No template —</option>
          {templates.map((tmpl) => <option key={tmpl.id} value={tmpl.id}>{tmpl.name}</option>)}
        </select>
        <p className={styles.templateHint} style={{ color: t.textFaint }}>Required for auto-respond to work</p>
      </div>

      <div className={styles.checkboxGroup}>
        <input id="auto_respond_enabled" type="checkbox" {...register('auto_respond_enabled')} disabled={isSubmitting} className={styles.checkbox} style={{ accentColor: t.accent }} />
        <label htmlFor="auto_respond_enabled" className={styles.checkboxLabel} style={{ color: t.text }}>Auto-respond enabled</label>
      </div>

      <div className={styles.formActions}>
        <button type="button" onClick={onCancel} disabled={isSubmitting} style={{ ...t.btnSecondary, opacity: isSubmitting ? 0.5 : 1 }}>Cancel</button>
        <button type="submit" disabled={isSubmitting} style={{ ...t.btnPrimary, opacity: isSubmitting ? 0.5 : 1 }}>
          {isSubmitting ? 'Saving…' : isEditMode ? 'Update Lead Source' : 'Create Lead Source'}
        </button>
      </div>
    </form>
  );
};
