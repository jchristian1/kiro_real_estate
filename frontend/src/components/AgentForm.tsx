import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface Company { id: number; name: string; }

const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

// Single flat form schema — app_password optional (required enforced manually for create)
const formSchema = z.object({
  agent_id: z.string().min(1, 'Agent ID is required').max(100)
    .regex(/^[a-zA-Z0-9._-]+$/, 'Only letters, numbers, hyphens, underscores, and dots allowed'),
  email: z.string().min(1, 'Email is required').regex(EMAIL_REGEX, 'Invalid email address'),
  app_password: z.string().optional(),
  display_name: z.string().max(255).optional(),
  phone: z.string().max(50).optional(),
  company_id: z.string().optional(), // kept as string; converted to number before submit
});

type FormValues = z.infer<typeof formSchema>;

// What we send to the parent — company_id as number | null
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

const FormField: React.FC<{ label: string; htmlFor: string; error?: string; required?: boolean; hint?: string; children: React.ReactNode }> = ({ label, htmlFor, error, required, hint, children }) => (
  <div className="mb-4">
    <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1">
      {label}{required && <span className="text-red-500 ml-1">*</span>}
    </label>
    {hint && <p className="text-xs text-gray-500 mb-1">{hint}</p>}
    {children}
    {error && <p className="mt-1 text-sm text-red-600" role="alert">{error}</p>}
  </div>
);

const inputClass = (hasError: boolean) =>
  `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${hasError ? 'border-red-500' : 'border-gray-300'}`;

export const AgentForm: React.FC<AgentFormProps> = ({
  initialValues, isEditMode = false, onSubmit, onCancel, isSubmitting = false, serverError,
}) => {
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    axios.get<{ companies: Company[] }>(`${API_BASE_URL}/companies`)
      .then((r) => setCompanies(r.data.companies))
      .catch(() => {});
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
    // Enforce app_password required on create
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

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} noValidate aria-label="Agent form">
      {serverError && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded" role="alert">{serverError}</div>
      )}

      <FormField label="Agent ID" htmlFor="agent_id" error={errors.agent_id?.message} required
        hint="Letters, numbers, hyphens, underscores, and dots only. No spaces.">
        <input id="agent_id" type="text" {...register('agent_id')} disabled={isEditMode || isSubmitting}
          placeholder="e.g. my_gmail" className={inputClass(!!errors.agent_id)} />
      </FormField>

      <FormField label="Gmail Address" htmlFor="email" error={errors.email?.message} required>
        <input id="email" type="email" {...register('email')} disabled={isSubmitting}
          placeholder="you@gmail.com" className={inputClass(!!errors.email)} />
      </FormField>

      <FormField
        label="Gmail App Password"
        htmlFor="app_password"
        error={errors.app_password?.message}
        required={!isEditMode}
        hint={isEditMode ? 'Leave blank to keep existing password' : 'Generate at myaccount.google.com/apppasswords — requires 2-Step Verification'}
      >
        <input id="app_password" type="password" {...register('app_password')} disabled={isSubmitting}
          placeholder={isEditMode ? '(unchanged)' : '16-character app password'} className={inputClass(!!errors.app_password)} />
      </FormField>

      <FormField label="Display Name" htmlFor="display_name" error={errors.display_name?.message}
        hint="Used in email templates as {agent_name}">
        <input id="display_name" type="text" {...register('display_name')} disabled={isSubmitting}
          placeholder="e.g. John Smith" className={inputClass(!!errors.display_name)} />
      </FormField>

      <FormField label="Phone Number" htmlFor="phone" error={errors.phone?.message}
        hint="Used in email templates as {agent_phone}">
        <input id="phone" type="tel" {...register('phone')} disabled={isSubmitting}
          placeholder="e.g. 555-123-4567" className={inputClass(!!errors.phone)} />
      </FormField>

      <FormField label="Company" htmlFor="company_id">
        <select id="company_id" {...register('company_id')} disabled={isSubmitting} className={inputClass(false)}>
          <option value="">— No company —</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </FormField>

      <div className="flex justify-end gap-3 mt-6">
        <button type="button" onClick={onCancel} disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
          Cancel
        </button>
        <button type="submit" disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
          {isSubmitting ? 'Saving...' : isEditMode ? 'Update Agent' : 'Create Agent'}
        </button>
      </div>
    </form>
  );
};
