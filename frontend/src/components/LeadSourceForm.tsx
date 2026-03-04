import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

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

export interface Template {
  id: number;
  name: string;
}

export interface LeadSourceFormProps {
  initialValues?: Partial<LeadSourceFormValues>;
  isEditMode?: boolean;
  onSubmit: (data: LeadSourceFormValues) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
  serverError?: string | null;
  templates?: Template[];
}

const FormField: React.FC<{ label: string; htmlFor: string; error?: string; required?: boolean; children: React.ReactNode }> = ({ label, htmlFor, error, required, children }) => (
  <div className="mb-4">
    <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1">
      {label}{required && <span className="text-red-500 ml-1">*</span>}
    </label>
    {children}
    {error && <p className="mt-1 text-sm text-red-600" role="alert">{error}</p>}
  </div>
);

const inputClass = (hasError: boolean) =>
  `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${hasError ? 'border-red-500' : 'border-gray-300'}`;

export const LeadSourceForm: React.FC<LeadSourceFormProps> = ({
  initialValues, isEditMode = false, onSubmit, onCancel, isSubmitting = false, serverError, templates = [],
}) => {
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

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Lead source form">
      {serverError && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded" role="alert">{serverError}</div>
      )}

      <FormField label="Sender Email" htmlFor="sender_email" error={errors.sender_email?.message} required>
        <input id="sender_email" type="email" {...register('sender_email')} disabled={isSubmitting}
          placeholder="leads@zillow.com" className={inputClass(!!errors.sender_email)} />
      </FormField>

      <FormField label="Identifier Snippet" htmlFor="identifier_snippet" error={errors.identifier_snippet?.message} required>
        <input id="identifier_snippet" type="text" {...register('identifier_snippet')} disabled={isSubmitting}
          placeholder="e.g. New Lead Notification" className={inputClass(!!errors.identifier_snippet)} />
      </FormField>

      <FormField label="Name Regex" htmlFor="name_regex" error={errors.name_regex?.message} required>
        <input id="name_regex" type="text" {...register('name_regex')} disabled={isSubmitting}
          placeholder="e.g. Name:\s*(.+)" className={`${inputClass(!!errors.name_regex)} font-mono text-sm`} />
      </FormField>

      <FormField label="Phone Regex" htmlFor="phone_regex" error={errors.phone_regex?.message} required>
        <input id="phone_regex" type="text" {...register('phone_regex')} disabled={isSubmitting}
          placeholder="e.g. Phone:\s*([\d\-\(\)\s]+)" className={`${inputClass(!!errors.phone_regex)} font-mono text-sm`} />
      </FormField>

      <FormField label="Response Template" htmlFor="template_id" error={errors.template_id?.message}>
        <select id="template_id" disabled={isSubmitting}
          className={inputClass(!!errors.template_id)}
          {...register('template_id', { setValueAs: (v) => (v === '' || v === null ? null : Number(v)) })}>
          <option value="">— No template —</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">Required for auto-respond to work</p>
      </FormField>

      <div className="mb-4 flex items-center gap-2">
        <input id="auto_respond_enabled" type="checkbox" {...register('auto_respond_enabled')}
          disabled={isSubmitting} className="h-4 w-4 text-blue-600 border-gray-300 rounded" />
        <label htmlFor="auto_respond_enabled" className="text-sm font-medium text-gray-700">Auto-respond enabled</label>
      </div>

      <div className="flex justify-end gap-3 mt-6">
        <button type="button" onClick={onCancel} disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
          Cancel
        </button>
        <button type="submit" disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
          {isSubmitting ? 'Saving...' : isEditMode ? 'Update Lead Source' : 'Create Lead Source'}
        </button>
      </div>
    </form>
  );
};
