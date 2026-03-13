/**
 * Unit tests for RegexTestHarness component
 *
 * Requirements: 2.3, 2.4, 14.5, 14.6, 14.7, 23.1, 23.2
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { RegexTestHarness } from './RegexTestHarness';

vi.mock('axios');

const makeResponse = (result: object) => ({
  data: { pattern: 'test', test_text: 'sample', result },
});

describe('RegexTestHarness', () => {
  const user = userEvent.setup();

  beforeEach(() => { vi.clearAllMocks(); });

  describe('Rendering', () => {
    it('renders pattern and sample text inputs', () => {
      render(<RegexTestHarness />);
      expect(screen.getByTestId('pattern-input')).toBeInTheDocument();
      expect(screen.getByTestId('test-text-input')).toBeInTheDocument();
    });

    it('renders Test Pattern button', () => {
      render(<RegexTestHarness />);
      expect(screen.getByTestId('test-button')).toBeInTheDocument();
    });

    it('pre-fills pattern from initialPattern prop', () => {
      render(<RegexTestHarness initialPattern="(?i)zillow" />);
      expect(screen.getByTestId('pattern-input')).toHaveValue('(?i)zillow');
    });

    it('disables button when pattern is empty', () => {
      render(<RegexTestHarness />);
      expect(screen.getByTestId('test-button')).toBeDisabled();
    });

    it('disables button when test text is empty', async () => {
      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), 'foo');
      expect(screen.getByTestId('test-button')).toBeDisabled();
    });

    it('enables button when both fields have values', async () => {
      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), 'foo');
      await user.type(screen.getByTestId('test-text-input'), 'foobar');
      expect(screen.getByTestId('test-button')).not.toBeDisabled();
    });
  });

  describe('Match found', () => {
    beforeEach(() => {
      vi.spyOn(axios, 'post').mockResolvedValue(
        makeResponse({
          matched: true,
          match_text: 'zillow',
          groups: ['zillow'],
          named_groups: {},
        })
      );
    });

    it('shows "Match found" status badge', async () => {
      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), '(?i)zillow');
      await user.type(screen.getByTestId('test-text-input'), 'New lead from zillow today');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('match-status')).toHaveTextContent('Match found');
      });
    });

    it('shows highlighted text section', async () => {
      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), '(?i)zillow');
      await user.type(screen.getByTestId('test-text-input'), 'New lead from zillow today');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('highlighted-text')).toBeInTheDocument();
      });
    });

    it('shows captured groups', async () => {
      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), '(zillow)');
      await user.type(screen.getByTestId('test-text-input'), 'lead from zillow');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('captured-groups')).toBeInTheDocument();
        expect(screen.getByTestId('group-1')).toHaveTextContent('zillow');
      });
    });
  });

  describe('Named groups', () => {
    it('shows named captured groups', async () => {
      vi.spyOn(axios, 'post').mockResolvedValue(
        makeResponse({
          matched: true,
          match_text: 'zillow',
          groups: [],
          named_groups: { source: 'zillow' },
        })
      );

      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), '(?P<source>zillow)');
      await user.type(screen.getByTestId('test-text-input'), 'lead from zillow');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('named-group-source')).toHaveTextContent('zillow');
      });
    });
  });

  describe('No match', () => {
    it('shows "No match" status badge', async () => {
      vi.spyOn(axios, 'post').mockResolvedValue(
        makeResponse({ matched: false, match_text: null, groups: [], named_groups: {} })
      );

      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), 'zillow');
      await user.type(screen.getByTestId('test-text-input'), 'realtor lead');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('match-status')).toHaveTextContent('No match');
      });
    });

    it('does not show highlighted text when no match', async () => {
      vi.spyOn(axios, 'post').mockResolvedValue(
        makeResponse({ matched: false, match_text: null, groups: [], named_groups: {} })
      );

      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), 'zillow');
      await user.type(screen.getByTestId('test-text-input'), 'realtor lead');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.queryByTestId('highlighted-text')).not.toBeInTheDocument();
      });
    });
  });

  describe('Timeout error', () => {
    it('shows timeout error message for 408 response', async () => {
      vi.spyOn(axios, 'post').mockRejectedValue(
        { response: { status: 408, data: { detail: 'Timeout' } } }
      );

      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), '(a+)+');
      await user.type(screen.getByTestId('test-text-input'), 'aaaaaaaaaaaaaaab');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('test-error')).toHaveTextContent('timed out');
      });
    });
  });

  describe('API error', () => {
    it('shows error message on API failure', async () => {
      vi.spyOn(axios, 'post').mockRejectedValue(
        { response: { status: 400, data: { detail: 'Invalid regex syntax' } } }
      );

      render(<RegexTestHarness />);
      fireEvent.change(screen.getByTestId('pattern-input'), { target: { value: '[bad' } });
      await user.type(screen.getByTestId('test-text-input'), 'some text');
      await user.click(screen.getByTestId('test-button'));

      await waitFor(() => {
        expect(screen.getByTestId('test-error')).toHaveTextContent('Invalid regex syntax');
      });
    });
  });

  describe('Loading state', () => {
    it('shows "Testing..." while request is in flight', async () => {
      vi.spyOn(axios, 'post').mockImplementation(() => new Promise(() => {}));

      render(<RegexTestHarness />);
      await user.type(screen.getByTestId('pattern-input'), 'foo');
      await user.type(screen.getByTestId('test-text-input'), 'foobar');
      await user.click(screen.getByTestId('test-button'));

      expect(screen.getByTestId('test-button')).toHaveTextContent('Testing...');
      expect(screen.getByTestId('test-button')).toBeDisabled();
    });
  });
});
