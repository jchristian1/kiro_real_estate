/**
 * TemplateEditor Component
 * Requirements: 3.3, 3.5
 */
import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

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
  const { register, handleSubmit, setValue, getValues, formState: { errors } } = useForm<TemplateFormValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: { name: initialValues?.name ?? '', subject: initialValues?.subject ?? '', body: initialValues?.body ?? '' },
  });

  const insertPlaceholder = (field: 'subject' | 'body', placeholder: string) => {
    const current = getValues(field);
    setValue(field, current + placeholder, { shouldValidate: true });
  };

  const inputCls = (err?: string) =>
    `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${err ? 'border-red-500' : 'border-gray-300'}`;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Template editor form" data-testid="template-editor-form">
      {serverError && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded" role="alert" data-testid="server-error">{serverError}</div>
      )}

      {/* Placeholder buttons */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Available Placeholders</p>
        <div className="flex flex-wrap gap-2" data-testid="placeholder-buttons">
          {PLACEHOLDERS.map((p) => (
            <div key={p} className="flex gap-1">
              <button type="button" onClick={() => insertPlaceholder('subject', p)}
                className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded font-mono" data-testid={`insert-subject-${p}`}>
                +Subject
              </button>
              <button type="button" onClick={() => insertPlaceholder('body', p)}
                className="px-2 py-1 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded font-mono" data-testid={`insert-body-${p}`}>
                {p}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Name <span className="text-red-500">*</span></label>
        <input id="name" type="text" {...register('name')} disabled={isSubmitting} className={inputCls(errors.name?.message)} data-testid="name-input" />
        {errors.name && <p className="mt-1 text-sm text-red-600" role="alert" data-testid="error-name">{errors.name.message}</p>}
      </div>

      <div className="mb-4">
        <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">Subject <span className="text-red-500">*</span></label>
        <input id="subject" type="text" {...register('subject')} disabled={isSubmitting} className={inputCls(errors.subject?.message)} data-testid="subject-input" />
        {errors.subject && <p className="mt-1 text-sm text-red-600" role="alert" data-testid="error-subject">{errors.subject.message}</p>}
      </div>

      <div className="mb-4">
        <label htmlFor="body" className="block text-sm font-medium text-gray-700 mb-1">Body <span className="text-red-500">*</span></label>
        <textarea id="body" rows={8} {...register('body')} disabled={isSubmitting} className={inputCls(errors.body?.message)} data-testid="body-input" />
        {errors.body && <p className="mt-1 text-sm text-red-600" role="alert" data-testid="error-body">{errors.body.message}</p>}
      </div>

      <div className="flex justify-end gap-3 mt-6">
        <button type="button" onClick={onCancel} disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
          Cancel
        </button>
        <button type="submit" disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50" data-testid="submit-button">
          {isSubmitting ? 'Saving...' : isEditMode ? 'Update Template' : 'Create Template'}
        </button>
      </div>
    </form>
  );
};
