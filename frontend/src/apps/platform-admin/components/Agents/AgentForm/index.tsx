import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import axios from 'axios';
import { useT } from '../../../../../shared/hooks/useT';
import { formSchema } from '@/shared/utils/helpers/agent-helper';
import { z } from 'zod';
import { Company } from '@/models/platform-admin/components/agent';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';

type FormValues = z.infer<typeof formSchema>;

export type AgentFormValues = Omit<FormValues, 'company_id'> & { company_id: number | null };
export type AgentEditFormValues = AgentFormValues;

export interface AgentFormProps {
  initialValues?: Partial<{ agent_id: string; email: string; display_name?: string; phone?: string; company_id?: number | null }>;
  isEditMode?: boolean;
  onSubmit: (data: AgentFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
  serverError?: string | null;
}

export const AgentForm: React.FC<AgentFormProps> = ({
  initialValues, isEditMode = false, onSubmit, onCancel, isSubmitting = false, serverError,
}) => {
  const t = useT();
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    axios.get<{ companies: Company[] }>(`${API_BASE_URL}/companies`)
      .then((r) => setCompanies(r.data.companies))
      .catch(() => { });
  }, []);

  const { register, handleSubmit, formState: { errors }, setError } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      agent_id: initialValues?.agent_id ?? '',
      email: initialValues?.email ?? '',
      app_password: '',
      display_name: initialValues?.display_name ?? '',
      phone: initialValues?.phone ?? '',
      company_id: initialValues?.company_id != null ? String(initialValues.company_id) : '',
    },
  });

  const handleFormSubmit = (data: FormValues) => {
    if (!isEditMode && !data.app_password) {
      setError('app_password', { message: 'App password is required' });
      return;
    }
    const payload: AgentFormValues = {
      ...data,
      company_id: data.company_id && data.company_id !== '' ? Number(data.company_id) : null,
    };
    return onSubmit(payload);
  };

  const fieldWrap = (
    label: string,
    htmlFor: string,
    required: boolean,
    hint: string | undefined,
    error: string | undefined,
    children: React.ReactNode
  ) => (
    <div style={{ marginBottom: 16 }}>
      <label htmlFor={htmlFor} style={{ display: 'block', fontSize: 12, fontWeight: 600, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 5 }}>
        {label}{required && <span style={{ color: t.red, marginLeft: 4 }}>*</span>}
      </label>
      {hint && <p style={{ margin: '0 0 5px', fontSize: 11, color: t.textMuted }}>{hint}</p>}
      {children}
      {error && <p role="alert" style={{ margin: '5px 0 0', fontSize: 12, color: t.red }}>{error}</p>}
    </div>
  );

  const inputStyle = (hasError: boolean): React.CSSProperties => ({
    ...t.input,
    borderColor: hasError ? t.red : t.border,
  });

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} noValidate aria-label="Agent form">
      {serverError && (
        <div role="alert" style={{ marginBottom: 16, padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 10, fontSize: 13, color: t.red }}>
          {serverError}
        </div>
      )}

      {fieldWrap('Agent ID', 'agent_id', true, 'Letters, numbers, hyphens, underscores, and dots only. No spaces.', errors.agent_id?.message,
        <input id="agent_id" type="text" {...register('agent_id')} disabled={isEditMode || isSubmitting}
          placeholder="e.g. my_gmail" style={{ ...inputStyle(!!errors.agent_id), opacity: (isEditMode || isSubmitting) ? 0.6 : 1 }} />
      )}

      {fieldWrap('Gmail Address', 'email', true, undefined, errors.email?.message,
        <input id="email" type="email" {...register('email')} disabled={isSubmitting}
          placeholder="you@gmail.com" style={{ ...inputStyle(!!errors.email), opacity: isSubmitting ? 0.6 : 1 }} />
      )}

      {fieldWrap(
        'Gmail App Password', 'app_password', !isEditMode,
        isEditMode ? 'Leave blank to keep existing password' : 'Generate at myaccount.google.com/apppasswords — requires 2-Step Verification',
        errors.app_password?.message,
        <input id="app_password" type="password" {...register('app_password')} disabled={isSubmitting}
          placeholder={isEditMode ? '(unchanged)' : '16-character app password'} style={{ ...inputStyle(!!errors.app_password), opacity: isSubmitting ? 0.6 : 1 }} />
      )}

      {fieldWrap('Display Name', 'display_name', false, 'Used in email templates as {agent_name}', errors.display_name?.message,
        <input id="display_name" type="text" {...register('display_name')} disabled={isSubmitting}
          placeholder="e.g. John Smith" style={{ ...inputStyle(!!errors.display_name), opacity: isSubmitting ? 0.6 : 1 }} />
      )}

      {fieldWrap('Phone Number', 'phone', false, 'Used in email templates as {agent_phone}', errors.phone?.message,
        <input id="phone" type="tel" {...register('phone')} disabled={isSubmitting}
          placeholder="e.g. 555-123-4567" style={{ ...inputStyle(!!errors.phone), opacity: isSubmitting ? 0.6 : 1 }} />
      )}

      {fieldWrap('Company', 'company_id', false, undefined, undefined,
        <select id="company_id" {...register('company_id')} disabled={isSubmitting}
          style={{ ...inputStyle(false), opacity: isSubmitting ? 0.6 : 1 }}>
          <option value="">— No company —</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 24 }}>
        <button type="button" onClick={onCancel} disabled={isSubmitting}
          style={{ ...t.btnSecondary, opacity: isSubmitting ? 0.5 : 1 }}>
          Cancel
        </button>
        <button type="submit" disabled={isSubmitting}
          style={{ ...t.btnPrimary, opacity: isSubmitting ? 0.5 : 1 }}>
          {isSubmitting ? 'Saving...' : isEditMode ? 'Update Agent' : 'Create Agent'}
        </button>
      </div>
    </form>
  );
};
