/**
 * Tests for ToastContainer and ToastContext
 * Requirements: 23.4
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ToastProvider, useToast } from '../../../shared/contexts/ToastContext';
import { ToastContainer } from './ToastContainer';
import React from 'react';

// Helper component to trigger toasts
const ToastTrigger: React.FC<{ type?: 'success' | 'error' | 'info' | 'warning'; message?: string }> = ({
  type = 'success',
  message = 'Test message',
}) => {
  const toast = useToast();
  return (
    <button
      data-testid="trigger"
      onClick={() => {
        if (type === 'success') toast.success(message);
        else if (type === 'error') toast.error(message);
        else if (type === 'info') toast.info(message);
        else toast.warning(message);
      }}
    >
      Show Toast
    </button>
  );
};

const renderWithProvider = (type?: 'success' | 'error' | 'info' | 'warning', message?: string) =>
  render(
    <ToastProvider>
      <ToastContainer />
      <ToastTrigger type={type} message={message} />
    </ToastProvider>
  );

describe('ToastContainer', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('renders nothing when no toasts', () => {
    renderWithProvider();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a success toast', () => {
    renderWithProvider('success', 'Saved successfully');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Saved successfully')).toBeInTheDocument();
  });

  it('shows an error toast', () => {
    renderWithProvider('error', 'Something went wrong');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows an info toast', () => {
    renderWithProvider('info', 'Info message');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Info message')).toBeInTheDocument();
  });

  it('shows a warning toast', () => {
    renderWithProvider('warning', 'Warning message');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Warning message')).toBeInTheDocument();
  });

  it('dismisses toast on close button click', () => {
    renderWithProvider('success', 'Dismiss me');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Dismiss me')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Dismiss'));
    expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument();
  });

  it('auto-dismisses success toast after 3 seconds', () => {
    renderWithProvider('success', 'Auto dismiss');
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getByText('Auto dismiss')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(3000));
    expect(screen.queryByText('Auto dismiss')).not.toBeInTheDocument();
  });

  it('error toast does not auto-dismiss', () => {
    renderWithProvider('error', 'Persistent error');
    fireEvent.click(screen.getByTestId('trigger'));
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByText('Persistent error')).toBeInTheDocument();
  });

  it('can show multiple toasts', () => {
    renderWithProvider('success', 'First');
    fireEvent.click(screen.getByTestId('trigger'));
    fireEvent.click(screen.getByTestId('trigger'));
    expect(screen.getAllByRole('alert')).toHaveLength(2);
  });
});

describe('getFriendlyErrorMessage', () => {
  it('returns friendly message for 401', async () => {
    const { getFriendlyErrorMessage } = await import('../../../shared/api/client');
    const err = { isAxiosError: true, response: { status: 401, data: {} } };
    // Use axios.isAxiosError mock
    expect(getFriendlyErrorMessage(err as unknown as Error)).toContain('session has expired');
  });

  it('returns friendly message for 403', async () => {
    const { getFriendlyErrorMessage } = await import('../../../shared/api/client');
    const err = { isAxiosError: true, response: { status: 403, data: {} } };
    expect(getFriendlyErrorMessage(err as unknown as Error)).toContain('permission');
  });

  it('returns friendly message for 500', async () => {
    const { getFriendlyErrorMessage } = await import('../../../shared/api/client');
    const err = { isAxiosError: true, response: { status: 500, data: {} } };
    expect(getFriendlyErrorMessage(err as unknown as Error)).toContain('internal server error');
  });

  it('returns network error message when no response', async () => {
    const { getFriendlyErrorMessage } = await import('../../../shared/api/client');
    const err = { isAxiosError: true, response: undefined };
    expect(getFriendlyErrorMessage(err as unknown as Error)).toContain('connect to the server');
  });
});
