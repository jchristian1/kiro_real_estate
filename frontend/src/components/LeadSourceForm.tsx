import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useT } from '../utils/useT';

const isValidRegex = (val: string) => { try { new RegExp(val); return true; } catch { return false; } };

const leadSourceSchema = z.object({
  sender_email: z.string().min(1, 'Sender email is required').email('Invalid email address'),
  identifier_snippet: z.string().min(1, 'Identifier snippet is required'),
  name_regex: z.string().min(1, 'Name regex is required').refine(isValidRegex, 'Invalid regex syntax'),
  phone_regex: z.string().min(1, 'Phone regex is required').refine(isValidRegex, 'Invalid regex syntax'),
  template_id: z.number().nullable().optional(),
  auto_respond_enabled: z.boolean(),
});

export type LeadSourceFormValues = z.infer<typeof leadSourceSchema>;

export interface Template { id: number; name: string; }

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
        <div style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}40`, color: t.red, borderRadius: 10, fontSize: 13 }} role="alert">{serverError}</div>
      )}

      {[
        { id: 'sender_email', label: 'Sender Email', type: 'email', placeholder: 'leads@zillow.com', error: errors.sender_email?.message, mono: false },
        { id: 'identifier_snippet', label: 'Identifier Snippet', type: 'text', placeholder: 'e.g. New Lead Notification', error: errors.identifier_snippet?.message, mono: false },
        { id: 'name_regex', label: 'Name Regex', type: 'text', placeholder: 'e.g. Name:\\s*(.+)', error: errors.name_regex?.message, mono: true },
        { id: 'phone_regex', label: 'Phone Regex', type: 'text', placeholder: 'e.g. Phone:\\s*([\\d\\-\\(\\)\\s]+)', error: errors.phone_regex?.message, mono: true },
      ].map(({ id, label, type, placeholder, error, mono }) => (
        <div key={id} style={{ marginBottom: 16 }}>
          <label htmlFor={id} style={t.labelStyle}>{label} <span style={{ color: t.red }}>*</span></label>
          <input id={id} type={type} {...register(id as keyof LeadSourceFormValues)} disabled={isSubmitting}
            placeholder={placeholder} style={{ ...fieldStyle(!!error), fontFamily: mono ? 'monospace' : 'inherit' }} />
          {error && <p style={{ marginTop: 4, fontSize: 12, color: t.red }} role="alert">{error}</p>}
        </div>
      ))}

      <div style={{ marginBottom: 16 }}>
        <label htmlFor="template_id" style={t.labelStyle}>Response Template</label>
        <select id="template_id" disabled={isSubmitting} style={fieldStyle(!!errors.template_id)}
          {...register('template_id', { setValueAs: (v) => (v === '' || v === null ? null : Number(v)) })}>
          <option value="">— No template —</option>
          {templates.map((tmpl) => <option key={tmpl.id} value={tmpl.id}>{tmpl.name}</option>)}
        </select>
        <p style={{ marginTop: 4, fontSize: 11, color: t.textFaint }}>Required for auto-respond to work</p>
      </div>

      <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <input id="auto_respond_enabled" type="checkbox" {...register('auto_respond_enabled')} disabled={isSubmitting} style={{ accentColor: t.accent, width: 16, height: 16 }} />
        <label htmlFor="auto_respond_enabled" style={{ fontSize: 13, color: t.text, cursor: 'pointer' }}>Auto-respond enabled</label>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        <button type="button" onClick={onCancel} disabled={isSubmitting} style={{ ...t.btnSecondary, opacity: isSubmitting ? 0.5 : 1 }}>Cancel</button>
        <button type="submit" disabled={isSubmitting} style={{ ...t.btnPrimary, opacity: isSubmitting ? 0.5 : 1 }}>
          {isSubmitting ? 'Saving…' : isEditMode ? 'Update Lead Source' : 'Create Lead Source'}
        </button>
      </div>
    </form>
  );
};
