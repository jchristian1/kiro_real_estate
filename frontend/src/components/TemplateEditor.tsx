import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useT } from '../utils/useT';

const PLACEHOLDERS = ['{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'];

const templateSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  subject: z.string().min(1, 'Subject is required').max(500)
    .refine((v) => !v.includes('\n') && !v.includes('\r'), 'Subject cannot contain newlines'),
  body: z.string().min(1, 'Body is required'),
});

export type TemplateFormValues = z.infer<typeof templateSchema>;

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
        <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}40`, color: t.red, borderRadius: 10, fontSize: 13 }} role="alert" data-testid="server-error">{serverError}</div>
      )}

      <div style={{ marginBottom: 16 }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Available Placeholders</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }} data-testid="placeholder-buttons">
          {PLACEHOLDERS.map((p) => (
            <div key={p} style={{ display: 'flex', gap: 4 }}>
              <button type="button" onClick={() => insertPlaceholder('subject', p)}
                style={{ padding: '3px 8px', fontSize: 11, background: t.bgBadge, color: t.textMuted, border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'monospace' }}
                data-testid={`insert-subject-${p}`}>+Subject</button>
              <button type="button" onClick={() => insertPlaceholder('body', p)}
                style={{ padding: '3px 8px', fontSize: 11, background: t.accentBg, color: t.accent, border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'monospace' }}
                data-testid={`insert-body-${p}`}>{p}</button>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label htmlFor="name" style={t.labelStyle}>Name <span style={{ color: t.red }}>*</span></label>
        <input id="name" type="text" {...register('name')} disabled={isSubmitting} style={fieldStyle(!!errors.name?.message)} data-testid="name-input" />
        {errors.name && <p style={{ marginTop: 4, fontSize: 12, color: t.red }} role="alert" data-testid="error-name">{errors.name.message}</p>}
      </div>

      <div style={{ marginBottom: 16 }}>
        <label htmlFor="subject" style={t.labelStyle}>Subject <span style={{ color: t.red }}>*</span></label>
        <input id="subject" type="text" {...register('subject')} disabled={isSubmitting} style={fieldStyle(!!errors.subject?.message)} data-testid="subject-input" />
        {errors.subject && <p style={{ marginTop: 4, fontSize: 12, color: t.red }} role="alert" data-testid="error-subject">{errors.subject.message}</p>}
      </div>

      <div style={{ marginBottom: 16 }}>
        <label htmlFor="body" style={t.labelStyle}>Body <span style={{ color: t.red }}>*</span></label>
        <textarea id="body" rows={8} {...register('body')} disabled={isSubmitting} style={fieldStyle(!!errors.body?.message)} data-testid="body-input" />
        {errors.body && <p style={{ marginTop: 4, fontSize: 12, color: t.red }} role="alert" data-testid="error-body">{errors.body.message}</p>}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        <button type="button" onClick={onCancel} disabled={isSubmitting} style={{ ...t.btnSecondary, opacity: isSubmitting ? 0.5 : 1 }}>Cancel</button>
        <button type="submit" disabled={isSubmitting} style={{ ...t.btnPrimary, opacity: isSubmitting ? 0.5 : 1 }} data-testid="submit-button">
          {isSubmitting ? 'Saving…' : isEditMode ? 'Update Template' : 'Create Template'}
        </button>
      </div>
    </form>
  );
};
