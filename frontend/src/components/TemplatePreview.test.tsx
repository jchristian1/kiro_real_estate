/**
 * Tests for TemplatePreview component
 * Requirements: 23.4
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { TemplatePreview } from './TemplatePreview';

vi.mock('axios');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedAxios = axios as any;

describe('TemplatePreview', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows empty state when no content', () => {
    render(<TemplatePreview subject="" body="" />);
    expect(screen.getByTestId('preview-empty')).toBeInTheDocument();
  });

  it('shows preview after API response', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({ data: { subject: 'Hello John Doe', body: 'Hi John Doe' } });
    render(<TemplatePreview subject="Hello {lead_name}" body="Hi {lead_name}" />);
    await waitFor(() => {
      expect(screen.getByTestId('preview-subject')).toHaveTextContent('Hello John Doe');
      expect(screen.getByTestId('preview-body')).toHaveTextContent('Hi John Doe');
    }, { timeout: 2000 });
  });

  it('shows error on API failure', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue({ response: { data: { detail: 'Invalid placeholder' } } });
    render(<TemplatePreview subject="Hello {bad}" body="Hi {bad}" />);
    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toHaveTextContent('Invalid placeholder');
    }, { timeout: 2000 });
  });
});
