import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useT } from '@/shared/hooks';
import { PLACEHOLDERS, TemplateFormValues, templateSchema } from '@/shared/utils';
import styles from './index.module.css';

export interface TemplateEditorProps {
  initialValues?: Partial<TemplateFormValues>;
  isEditMode?: boolean;
  onSubmit: (data: TemplateFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
  serverError?: string | null;
}

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  initialValues, isEditMode = false, onSubmit, onCancel, isSubmitting = false, serverError,
}) => {
  const t = useT();
  const { register, handleSubmit, setValue, getValues, formState: { errors } } = useForm<TemplateFormValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: { name: initialValues?.name ?? '', subject: initialValues?.subject ?? '', body: initialValues?.body ?? '' },
  });

  const insertPlaceholder = (field: 'subject' | 'body', placeholder: string) => {
    setValue(field, getValues(field) + placeholder, { shouldValidate: true });
  };

  const fieldStyle = (hasError: boolean): React.CSSProperties => ({
    ...t.input,
    borderColor: hasError ? t.red : t.border,
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Template editor form" data-testid="template-editor-form">
      {serverError && (
        <div className={styles.serverError} style={{ background: t.redBg, border: `1px solid ${t.red}40`, color: t.red }} role="alert" data-testid="server-error">{serverError}</div>
      )}

      <div className={styles.placeholderSection}>
        <p className={styles.placeholderLabel} style={{ color: t.textFaint }}>Available Placeholders</p>
        <div className={styles.placeholderRow} data-testid="placeholder-buttons">
          {PLACEHOLDERS.map((p) => (
            <div key={p} className={styles.placeholderBtnGroup}>
              <button type="button" onClick={() => insertPlaceholder('subject', p)}
                className={styles.placeholderBtn}
                style={{ background: t.bgBadge, color: t.textMuted }}
                data-testid={`insert-subject-${p}`}>+Subject</button>
              <button type="button" onClick={() => insertPlaceholder('body', p)}
                className={styles.placeholderBtn}
                style={{ background: t.accentBg, color: t.accent }}
                data-testid={`insert-body-${p}`}>{p}</button>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="name" style={t.labelStyle}>Name <span style={{ color: t.red }}>*</span></label>
        <input id="name" type="text" {...register('name')} disabled={isSubmitting} style={fieldStyle(!!errors.name?.message)} data-testid="name-input" />
        {errors.name && <p className={styles.fieldError} style={{ color: t.red }} role="alert" data-testid="error-name">{errors.name.message}</p>}
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="subject" style={t.labelStyle}>Subject <span style={{ color: t.red }}>*</span></label>
        <input id="subject" type="text" {...register('subject')} disabled={isSubmitting} style={fieldStyle(!!errors.subject?.message)} data-testid="subject-input" />
        {errors.subject && <p className={styles.fieldError} style={{ color: t.red }} role="alert" data-testid="error-subject">{errors.subject.message}</p>}
      </div>

      <div className={styles.fieldGroup}>
        <label htmlFor="body" style={t.labelStyle}>Body <span style={{ color: t.red }}>*</span></label>
        <textarea id="body" rows={8} {...register('body')} disabled={isSubmitting} style={fieldStyle(!!errors.body?.message)} data-testid="body-input" />
        {errors.body && <p className={styles.fieldError} style={{ color: t.red }} role="alert" data-testid="error-body">{errors.body.message}</p>}
      </div>

      <div className={styles.formActions}>
        <button type="button" onClick={onCancel} disabled={isSubmitting} style={{ ...t.btnSecondary, opacity: isSubmitting ? 0.5 : 1 }}>Cancel</button>
        <button type="submit" disabled={isSubmitting} style={{ ...t.btnPrimary, opacity: isSubmitting ? 0.5 : 1 }} data-testid="submit-button">
          {isSubmitting ? 'Saving…' : isEditMode ? 'Update Template' : 'Create Template'}
        </button>
      </div>
    </form>
  );
};
