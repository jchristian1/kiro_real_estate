/**
 * Unit tests for AgentForm component
 *
 * **Validates: Requirements 1.5, 23.5**
 *
 * Tests cover:
 * - Rendering in create and edit modes
 * - Required field validation
 * - Email format validation (RFC 5322)
 * - Inline validation error display
 * - Successful form submission
 * - Server-side error display
 * - Cancel action
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentForm } from './AgentForm';

const noop = () => Promise.resolve();

describe('AgentForm', () => {
  const user = userEvent.setup();

  describe('Create mode rendering', () => {
    it('renders all required fields', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      expect(screen.getByLabelText(/Agent ID/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Client ID/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Client Secret/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Refresh Token/i)).toBeInTheDocument();
    });

    it('renders Create Agent submit button', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      expect(screen.getByRole('button', { name: /Create Agent/i })).toBeInTheDocument();
    });

    it('renders Cancel button', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('does not show "leave blank" hint in create mode', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      expect(screen.queryByText(/leave blank to keep existing/i)).not.toBeInTheDocument();
    });
  });

  describe('Edit mode rendering', () => {
    const initialValues = {
      agent_id: 'agent1',
      email: 'agent1@example.com',
      gmail_client_id: '',
      gmail_client_secret: '',
      gmail_refresh_token: '',
    };

    it('renders Update Agent submit button', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isEditMode initialValues={initialValues} />);

      expect(screen.getByRole('button', { name: /Update Agent/i })).toBeInTheDocument();
    });

    it('pre-fills agent_id and email from initialValues', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isEditMode initialValues={initialValues} />);

      expect(screen.getByLabelText(/Agent ID/i)).toHaveValue('agent1');
      expect(screen.getByLabelText(/Email/i)).toHaveValue('agent1@example.com');
    });

    it('disables agent_id field in edit mode', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isEditMode initialValues={initialValues} />);

      expect(screen.getByLabelText(/Agent ID/i)).toBeDisabled();
    });

    it('shows "leave blank to keep existing" hint for credentials', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isEditMode initialValues={initialValues} />);

      expect(screen.getByText(/leave blank to keep existing/i)).toBeInTheDocument();
    });
  });

  describe('Required field validation', () => {
    it('shows error when agent_id is empty on submit', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-agent_id')).toHaveTextContent('Agent ID is required');
      });
    });

    it('shows error when email is empty on submit', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-email')).toHaveTextContent('Email is required');
      });
    });

    it('shows error when gmail_client_id is empty in create mode', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-gmail_client_id')).toHaveTextContent(
          'Gmail Client ID is required'
        );
      });
    });

    it('shows error when gmail_client_secret is empty in create mode', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-gmail_client_secret')).toHaveTextContent(
          'Gmail Client Secret is required'
        );
      });
    });

    it('shows error when gmail_refresh_token is empty in create mode', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-gmail_refresh_token')).toHaveTextContent(
          'Gmail Refresh Token is required'
        );
      });
    });
  });

  describe('Email format validation', () => {
    it('shows error for invalid email format', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Email/i), 'not-an-email');
      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-email')).toHaveTextContent(
          'Invalid email address format'
        );
      });
    });

    it('shows error for email missing domain', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Email/i), 'user@');
      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-email')).toHaveTextContent(
          'Invalid email address format'
        );
      });
    });

    it('shows error for email missing local part', async () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Email/i), '@example.com');
      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.getByTestId('error-email')).toHaveTextContent(
          'Invalid email address format'
        );
      });
    });

    it('accepts a valid email address', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<AgentForm onSubmit={onSubmit} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Agent ID/i), 'agent1');
      await user.type(screen.getByLabelText(/Email/i), 'valid@example.com');
      await user.type(screen.getByLabelText(/Client ID/i), 'client-id');
      await user.type(screen.getByLabelText(/Client Secret/i), 'client-secret');
      await user.type(screen.getByLabelText(/Refresh Token/i), 'refresh-token');

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('error-email')).not.toBeInTheDocument();
        expect(onSubmit).toHaveBeenCalledOnce();
      });
    });

    it('accepts email with subdomain', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<AgentForm onSubmit={onSubmit} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Agent ID/i), 'agent1');
      await user.type(screen.getByLabelText(/Email/i), 'user@mail.example.co.uk');
      await user.type(screen.getByLabelText(/Client ID/i), 'client-id');
      await user.type(screen.getByLabelText(/Client Secret/i), 'client-secret');
      await user.type(screen.getByLabelText(/Refresh Token/i), 'refresh-token');

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('error-email')).not.toBeInTheDocument();
        expect(onSubmit).toHaveBeenCalledOnce();
      });
    });
  });

  describe('Successful form submission', () => {
    it('calls onSubmit with correct data in create mode', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<AgentForm onSubmit={onSubmit} onCancel={noop} />);

      await user.type(screen.getByLabelText(/Agent ID/i), 'myagent');
      await user.type(screen.getByLabelText(/Email/i), 'myagent@example.com');
      await user.type(screen.getByLabelText(/Client ID/i), 'cid');
      await user.type(screen.getByLabelText(/Client Secret/i), 'csecret');
      await user.type(screen.getByLabelText(/Refresh Token/i), 'rtoken');

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            agent_id: 'myagent',
            email: 'myagent@example.com',
            gmail_client_id: 'cid',
            gmail_client_secret: 'csecret',
            gmail_refresh_token: 'rtoken',
          })
        );
      });
    });

    it('does not call onSubmit when validation fails', async () => {
      const onSubmit = vi.fn();
      render(<AgentForm onSubmit={onSubmit} onCancel={noop} />);

      await user.click(screen.getByRole('button', { name: /Create Agent/i }));

      await waitFor(() => {
        expect(onSubmit).not.toHaveBeenCalled();
      });
    });
  });

  describe('Cancel action', () => {
    it('calls onCancel when Cancel button is clicked', async () => {
      const onCancel = vi.fn();
      render(<AgentForm onSubmit={noop} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(onCancel).toHaveBeenCalledOnce();
    });
  });

  describe('Submitting state', () => {
    it('disables buttons while submitting', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isSubmitting />);

      expect(screen.getByRole('button', { name: /Saving.../i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    });

    it('shows "Saving..." text while submitting', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} isSubmitting />);

      expect(screen.getByRole('button', { name: /Saving.../i })).toBeInTheDocument();
    });
  });

  describe('Server error display', () => {
    it('displays server error message when provided', () => {
      render(
        <AgentForm onSubmit={noop} onCancel={noop} serverError="Agent ID already exists" />
      );

      expect(screen.getByTestId('server-error')).toHaveTextContent('Agent ID already exists');
    });

    it('does not display server error when not provided', () => {
      render(<AgentForm onSubmit={noop} onCancel={noop} />);

      expect(screen.queryByTestId('server-error')).not.toBeInTheDocument();
    });
  });
});
