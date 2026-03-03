/**
 * Unit tests for LeadSourceForm component
 *
 * Requirements: 2.2, 2.5, 23.4, 23.5
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LeadSourceForm } from './LeadSourceForm';

const noop = () => Promise.resolve();

describe('LeadSourceForm', () => {
  const user = userEvent.setup();

  describe('Rendering', () => {
    it('renders all fields', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      expect(screen.getByLabelText(/Name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Regex Pattern/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Description/i)).toBeInTheDocument();
    });

    it('renders Create Lead Source button in create mode', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      expect(screen.getByRole('button', { name: /Create Lead Source/i })).toBeInTheDocument();
    });

    it('renders Update Lead Source button in edit mode', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} isEditMode />);
      expect(screen.getByRole('button', { name: /Update Lead Source/i })).toBeInTheDocument();
    });

    it('pre-fills values in edit mode', () => {
      render(
        <LeadSourceForm
          onSubmit={noop}
          onCancel={noop}
          isEditMode
          initialValues={{ name: 'Zillow', regex_pattern: '(?i)zillow', description: 'Zillow leads' }}
        />
      );
      expect(screen.getByLabelText(/Name/i)).toHaveValue('Zillow');
      expect(screen.getByLabelText(/Regex Pattern/i)).toHaveValue('(?i)zillow');
      expect(screen.getByLabelText(/Description/i)).toHaveValue('Zillow leads');
    });
  });

  describe('Required field validation', () => {
    it('shows error when name is empty', async () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(screen.getByTestId('error-name')).toHaveTextContent('Name is required');
      });
    });

    it('shows error when regex_pattern is empty', async () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(screen.getByTestId('error-regex_pattern')).toHaveTextContent('Regex pattern is required');
      });
    });
  });

  describe('Regex pattern validation', () => {
    it('shows error for invalid regex syntax', async () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      fireEvent.change(screen.getByLabelText(/Regex Pattern/i), { target: { value: '[invalid(' } });
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(screen.getByTestId('error-regex_pattern')).toHaveTextContent('Invalid regex pattern syntax');
      });
    });

    it('accepts a valid regex pattern', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<LeadSourceForm onSubmit={onSubmit} onCancel={noop} />);
      await user.type(screen.getByLabelText(/Name/i), 'Zillow');
      await user.type(screen.getByLabelText(/Regex Pattern/i), 'zillow lead');
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(screen.queryByTestId('error-regex_pattern')).not.toBeInTheDocument();
        expect(onSubmit).toHaveBeenCalledOnce();
      });
    });

    it('accepts complex valid regex', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<LeadSourceForm onSubmit={onSubmit} onCancel={noop} />);
      await user.type(screen.getByLabelText(/Name/i), 'Complex');
      await user.type(screen.getByLabelText(/Regex Pattern/i), '^(foo|bar)\\s+\\d{3}$');
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(screen.queryByTestId('error-regex_pattern')).not.toBeInTheDocument();
        expect(onSubmit).toHaveBeenCalledOnce();
      });
    });
  });

  describe('Successful submission', () => {
    it('calls onSubmit with correct data', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      render(<LeadSourceForm onSubmit={onSubmit} onCancel={noop} />);
      await user.type(screen.getByLabelText(/Name/i), 'Zillow');
      await user.type(screen.getByLabelText(/Regex Pattern/i), 'zillow');
      await user.type(screen.getByLabelText(/Description/i), 'Zillow leads');
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'Zillow', regex_pattern: 'zillow', description: 'Zillow leads' })
        );
      });
    });

    it('does not call onSubmit when validation fails', async () => {
      const onSubmit = vi.fn();
      render(<LeadSourceForm onSubmit={onSubmit} onCancel={noop} />);
      await user.click(screen.getByRole('button', { name: /Create Lead Source/i }));
      await waitFor(() => expect(onSubmit).not.toHaveBeenCalled());
    });
  });

  describe('Cancel', () => {
    it('calls onCancel when Cancel is clicked', async () => {
      const onCancel = vi.fn();
      render(<LeadSourceForm onSubmit={noop} onCancel={onCancel} />);
      await user.click(screen.getByRole('button', { name: /Cancel/i }));
      expect(onCancel).toHaveBeenCalledOnce();
    });
  });

  describe('Server error', () => {
    it('displays server error when provided', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} serverError="Name already exists" />);
      expect(screen.getByTestId('server-error')).toHaveTextContent('Name already exists');
    });

    it('does not display server error when not provided', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} />);
      expect(screen.queryByTestId('server-error')).not.toBeInTheDocument();
    });
  });

  describe('Submitting state', () => {
    it('disables buttons while submitting', () => {
      render(<LeadSourceForm onSubmit={noop} onCancel={noop} isSubmitting />);
      expect(screen.getByRole('button', { name: /Saving.../i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    });
  });
});
