/**
 * Tests for TemplateEditor component
 * Requirements: 23.1, 23.4, 23.5
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TemplateEditor } from './TemplateEditor';

const noop = () => Promise.resolve();

describe('TemplateEditor', () => {
  const user = userEvent.setup();

  it('renders all fields', () => {
    render(<TemplateEditor onSubmit={noop} onCancel={noop} />);
    expect(screen.getByTestId('name-input')).toBeInTheDocument();
    expect(screen.getByTestId('subject-input')).toBeInTheDocument();
    expect(screen.getByTestId('body-input')).toBeInTheDocument();
  });

  it('shows placeholder buttons', () => {
    render(<TemplateEditor onSubmit={noop} onCancel={noop} />);
    expect(screen.getByTestId('placeholder-buttons')).toBeInTheDocument();
  });

  it('shows validation errors on empty submit', async () => {
    render(<TemplateEditor onSubmit={noop} onCancel={noop} />);
    await user.click(screen.getByTestId('submit-button'));
    await waitFor(() => {
      expect(screen.getByTestId('error-name')).toBeInTheDocument();
      expect(screen.getByTestId('error-subject')).toBeInTheDocument();
      expect(screen.getByTestId('error-body')).toBeInTheDocument();
    });
  });

  it('calls onSubmit with valid data', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<TemplateEditor onSubmit={onSubmit} onCancel={noop} />);
    await user.type(screen.getByTestId('name-input'), 'Welcome');
    await user.type(screen.getByTestId('subject-input'), 'Hello {lead_name}');
    await user.type(screen.getByTestId('body-input'), 'Hi {lead_name}, contact {agent_name}');
    await user.click(screen.getByTestId('submit-button'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  it('pre-fills values in edit mode', () => {
    render(<TemplateEditor initialValues={{ name: 'T1', subject: 'Subj', body: 'Body' }} isEditMode onSubmit={noop} onCancel={noop} />);
    expect(screen.getByTestId('name-input')).toHaveValue('T1');
    expect(screen.getByTestId('subject-input')).toHaveValue('Subj');
    expect(screen.getByTestId('body-input')).toHaveValue('Body');
  });

  it('shows server error', () => {
    render(<TemplateEditor onSubmit={noop} onCancel={noop} serverError="Duplicate name" />);
    expect(screen.getByTestId('server-error')).toHaveTextContent('Duplicate name');
  });

  it('calls onCancel', async () => {
    const onCancel = vi.fn();
    render(<TemplateEditor onSubmit={noop} onCancel={onCancel} />);
    await user.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('inserts placeholder into body', async () => {
    render(<TemplateEditor onSubmit={noop} onCancel={noop} />);
    await user.click(screen.getByTestId('insert-body-{lead_name}'));
    expect(screen.getByTestId('body-input')).toHaveValue('{lead_name}');
  });
});
