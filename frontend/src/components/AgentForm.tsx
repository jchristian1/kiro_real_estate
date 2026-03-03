/**
 * Agent Form Component
 *
 * Reusable form for creating and editing Gmail agents.
 * Supports both create and edit modes.
 *
 * Validates:
 * - Required fields (agent_id, email, Gmail credentials)
 * - Email format per RFC 5322
 * - Shows inline validation errors under each field
 *
 * Requirements: 1.5
 */

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

// RFC 5322-compliant email regex
const EMAIL_REGEX =
  /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

/**
 * Zod schema for agent form validation.
 * In edit mode, Gmail credential fields are optional (leave blank to keep existing).
 */
const createAgentSchema = z.object({
  agent_id: z
    .string()
    .min(1, 'Agent ID is required')
    .max(100, 'Agent ID must be 100 characters or fewer'),
  email: z
    .string()
    .min(1, 'Email is required')
    .regex(EMAIL_REGEX, 'Invalid email address format'),
  gmail_client_id: z
    .string()
    .min(1, 'Gmail Client ID is required'),
  gmail_client_secret: z
    .string()
    .min(1, 'Gmail Client Secret is required'),
  gmail_refresh_token: z
    .string()
    .min(1, 'Gmail Refresh Token is required'),
});

const editAgentSchema = z.object({
  agent_id: z
    .string()
    .min(1, 'Agent ID is required')
    .max(100, 'Agent ID must be 100 characters or fewer'),
  email: z
    .string()
    .min(1, 'Email is required')
    .regex(EMAIL_REGEX, 'Invalid email address format'),
  gmail_client_id: z.string().optional(),
  gmail_client_secret: z.string().optional(),
  gmail_refresh_token: z.string().optional(),
});

export type AgentFormValues = z.infer<typeof createAgentSchema>;
export type AgentEditFormValues = z.infer<typeof editAgentSchema>;

export interface AgentFormProps {
  /** Initial values for edit mode */
  initialValues?: Partial<AgentFormValues>;
  /** Whether the form is in edit mode */
  isEditMode?: boolean;
  /** Called with form data on successful submission */
  onSubmit: (data: AgentFormValues | AgentEditFormValues) => Promise<void>;
  /** Called when the user cancels */
  onCancel: () => void;
  /** Whether the form is currently submitting */
  isSubmitting?: boolean;
  /** Server-side error message to display */
  serverError?: string | null;
}

/**
 * Reusable field wrapper that shows a label and inline validation error.
 */
const FormField: React.FC<{
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}> = ({ label, htmlFor, error, required, children }) => (
  <div className="mb-4">
    <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1">
      {label}
      {required && <span className="text-red-500 ml-1" aria-hidden="true">*</span>}
    </label>
    {children}
    {error && (
      <p className="mt-1 text-sm text-red-600" role="alert" data-testid={`error-${htmlFor}`}>
        {error}
      </p>
    )}
  </div>
);

const inputClass = (hasError: boolean) =>
  `w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    hasError ? 'border-red-500 focus:ring-red-500' : 'border-gray-300'
  }`;

export const AgentForm: React.FC<AgentFormProps> = ({
  initialValues,
  isEditMode = false,
  onSubmit,
  onCancel,
  isSubmitting = false,
  serverError,
}) => {
  const schema = isEditMode ? editAgentSchema : createAgentSchema;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AgentFormValues | AgentEditFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      agent_id: initialValues?.agent_id ?? '',
      email: initialValues?.email ?? '',
      gmail_client_id: initialValues?.gmail_client_id ?? '',
      gmail_client_secret: initialValues?.gmail_client_secret ?? '',
      gmail_refresh_token: initialValues?.gmail_refresh_token ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Agent form">
      {/* Server-side error */}
      {serverError && (
        <div
          className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded"
          role="alert"
          data-testid="server-error"
        >
          {serverError}
        </div>
      )}

      {/* Agent ID */}
      <FormField
        label="Agent ID"
        htmlFor="agent_id"
        error={errors.agent_id?.message}
        required
      >
        <input
          id="agent_id"
          type="text"
          {...register('agent_id')}
          disabled={isEditMode || isSubmitting}
          placeholder="e.g. agent1"
          className={inputClass(!!errors.agent_id)}
          aria-describedby={errors.agent_id ? 'error-agent_id' : undefined}
        />
      </FormField>

      {/* Email */}
      <FormField
        label="Email"
        htmlFor="email"
        error={errors.email?.message}
        required
      >
        <input
          id="email"
          type="email"
          {...register('email')}
          disabled={isSubmitting}
          placeholder="agent@example.com"
          className={inputClass(!!errors.email)}
          aria-describedby={errors.email ? 'error-email' : undefined}
        />
      </FormField>

      {/* Gmail Credentials section */}
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Gmail Credentials
          {isEditMode && (
            <span className="ml-2 text-xs font-normal text-gray-500">
              (leave blank to keep existing)
            </span>
          )}
        </h3>
      </div>

      {/* Client ID */}
      <FormField
        label="Client ID"
        htmlFor="gmail_client_id"
        error={errors.gmail_client_id?.message}
        required={!isEditMode}
      >
        <input
          id="gmail_client_id"
          type="text"
          {...register('gmail_client_id')}
          disabled={isSubmitting}
          placeholder="Google OAuth2 Client ID"
          className={inputClass(!!errors.gmail_client_id)}
          aria-describedby={errors.gmail_client_id ? 'error-gmail_client_id' : undefined}
        />
      </FormField>

      {/* Client Secret */}
      <FormField
        label="Client Secret"
        htmlFor="gmail_client_secret"
        error={errors.gmail_client_secret?.message}
        required={!isEditMode}
      >
        <input
          id="gmail_client_secret"
          type="password"
          {...register('gmail_client_secret')}
          disabled={isSubmitting}
          placeholder="Google OAuth2 Client Secret"
          className={inputClass(!!errors.gmail_client_secret)}
          aria-describedby={errors.gmail_client_secret ? 'error-gmail_client_secret' : undefined}
        />
      </FormField>

      {/* Refresh Token */}
      <FormField
        label="Refresh Token"
        htmlFor="gmail_refresh_token"
        error={errors.gmail_refresh_token?.message}
        required={!isEditMode}
      >
        <input
          id="gmail_refresh_token"
          type="password"
          {...register('gmail_refresh_token')}
          disabled={isSubmitting}
          placeholder="Google OAuth2 Refresh Token"
          className={inputClass(!!errors.gmail_refresh_token)}
          aria-describedby={errors.gmail_refresh_token ? 'error-gmail_refresh_token' : undefined}
        />
      </FormField>

      {/* Actions */}
      <div className="flex justify-end gap-3 mt-6">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Saving...' : isEditMode ? 'Update Agent' : 'Create Agent'}
        </button>
      </div>
    </form>
  );
};
