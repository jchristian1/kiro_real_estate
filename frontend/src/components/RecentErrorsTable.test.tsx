/**
 * Unit tests for RecentErrorsTable component
 * 
 * **Validates: Requirements 23.4**
 * 
 * Tests cover:
 * - Display of error count
 * - Zero errors state with success icon
 * - Non-zero errors state with warning icon
 * - Navigation to audit logs
 * - Proper styling and messaging
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { RecentErrorsTable } from './RecentErrorsTable';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('RecentErrorsTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (errorCount: number) => {
    return render(
      <BrowserRouter>
        <RecentErrorsTable errorCount={errorCount} />
      </BrowserRouter>
    );
  };

  describe('Component Structure', () => {
    it('should render component title', () => {
      renderComponent(0);

      expect(screen.getByText('Recent Errors (24h)')).toBeInTheDocument();
    });

    it('should render view audit logs button', () => {
      renderComponent(0);

      expect(screen.getByRole('button', { name: /view audit logs/i })).toBeInTheDocument();
    });

    it('should apply correct styling classes', () => {
      const { container } = renderComponent(0);

      const mainContainer = container.firstChild;
      expect(mainContainer).toHaveClass('bg-white', 'rounded-lg', 'shadow', 'p-6');
    });
  });

  describe('Zero Errors State', () => {
    it('should display success message when error count is zero', () => {
      renderComponent(0);

      expect(screen.getByText('No errors in the last 24 hours')).toBeInTheDocument();
    });

    it('should display success icon when error count is zero', () => {
      const { container } = renderComponent(0);

      const successIcon = container.querySelector('.bg-green-100');
      expect(successIcon).toBeInTheDocument();
    });

    it('should display positive message when error count is zero', () => {
      renderComponent(0);

      expect(screen.getByText('System is running smoothly')).toBeInTheDocument();
    });

    it('should apply green styling for zero errors', () => {
      const { container } = renderComponent(0);

      const iconContainer = container.querySelector('.bg-green-100');
      expect(iconContainer).toBeInTheDocument();

      const checkIcon = iconContainer?.querySelector('.text-green-600');
      expect(checkIcon).toBeInTheDocument();
    });
  });

  describe('Non-Zero Errors State', () => {
    it('should display error count when errors exist', () => {
      renderComponent(5);

      expect(screen.getByText('5 errors detected')).toBeInTheDocument();
    });

    it('should display singular "error" for count of 1', () => {
      renderComponent(1);

      expect(screen.getByText('1 error detected')).toBeInTheDocument();
    });

    it('should display plural "errors" for count > 1', () => {
      renderComponent(10);

      expect(screen.getByText('10 errors detected')).toBeInTheDocument();
    });

    it('should display warning icon when errors exist', () => {
      const { container } = renderComponent(5);

      const warningIcon = container.querySelector('.bg-orange-100');
      expect(warningIcon).toBeInTheDocument();
    });

    it('should display instruction message when errors exist', () => {
      renderComponent(5);

      expect(screen.getByText('Click "View Audit Logs" to see details')).toBeInTheDocument();
    });

    it('should apply orange styling for errors', () => {
      const { container } = renderComponent(5);

      const iconContainer = container.querySelector('.bg-orange-100');
      expect(iconContainer).toBeInTheDocument();

      const warningIcon = iconContainer?.querySelector('.text-orange-600');
      expect(warningIcon).toBeInTheDocument();
    });
  });

  describe('Navigation Functionality', () => {
    it('should navigate to audit logs when button is clicked', async () => {
      const user = userEvent.setup();
      renderComponent(5);

      const viewLogsButton = screen.getByRole('button', { name: /view audit logs/i });
      await user.click(viewLogsButton);

      expect(mockNavigate).toHaveBeenCalledWith('/audit-logs');
    });

    it('should navigate to audit logs from zero errors state', async () => {
      const user = userEvent.setup();
      renderComponent(0);

      const viewLogsButton = screen.getByRole('button', { name: /view audit logs/i });
      await user.click(viewLogsButton);

      expect(mockNavigate).toHaveBeenCalledWith('/audit-logs');
    });

    it('should call navigate only once per click', async () => {
      const user = userEvent.setup();
      renderComponent(5);

      const viewLogsButton = screen.getByRole('button', { name: /view audit logs/i });
      await user.click(viewLogsButton);

      expect(mockNavigate).toHaveBeenCalledTimes(1);
    });
  });

  describe('Edge Cases', () => {
    it('should handle very large error counts', () => {
      renderComponent(9999);

      expect(screen.getByText('9999 errors detected')).toBeInTheDocument();
    });

    it('should handle error count of exactly 1', () => {
      renderComponent(1);

      expect(screen.getByText('1 error detected')).toBeInTheDocument();
      expect(screen.queryByText('1 errors detected')).not.toBeInTheDocument();
    });

    it('should handle error count of exactly 2', () => {
      renderComponent(2);

      expect(screen.getByText('2 errors detected')).toBeInTheDocument();
    });

    it('should maintain consistent layout between states', () => {
      const { container: zeroErrorsContainer } = renderComponent(0);
      const { container: withErrorsContainer } = renderComponent(5);

      // Both should have the same main container structure
      expect(zeroErrorsContainer.firstChild).toHaveClass('bg-white', 'rounded-lg', 'shadow', 'p-6');
      expect(withErrorsContainer.firstChild).toHaveClass('bg-white', 'rounded-lg', 'shadow', 'p-6');
    });
  });

  describe('Icon Display', () => {
    it('should display checkmark icon for zero errors', () => {
      const { container } = renderComponent(0);

      // Check for checkmark path in SVG
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      
      const path = svg?.querySelector('path');
      expect(path).toHaveAttribute('d', 'M5 13l4 4L19 7');
    });

    it('should display warning triangle icon for errors', () => {
      const { container } = renderComponent(5);

      // Check for warning triangle path in SVG
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      
      const path = svg?.querySelector('path');
      expect(path).toHaveAttribute('d', 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z');
    });

    it('should have correct icon size', () => {
      const { container } = renderComponent(0);

      const iconContainer = container.querySelector('.w-16.h-16');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  describe('Text Styling', () => {
    it('should apply correct text styling for zero errors', () => {
      renderComponent(0);

      const mainText = screen.getByText('No errors in the last 24 hours');
      expect(mainText).toHaveClass('text-lg', 'font-medium', 'text-gray-800');
    });

    it('should apply correct text styling for errors', () => {
      renderComponent(5);

      const mainText = screen.getByText('5 errors detected');
      expect(mainText).toHaveClass('text-lg', 'font-medium', 'text-gray-800');
    });

    it('should apply correct styling to secondary text', () => {
      renderComponent(0);

      const secondaryText = screen.getByText('System is running smoothly');
      expect(secondaryText).toHaveClass('text-sm', 'text-gray-500');
    });
  });

  describe('Button Styling', () => {
    it('should apply correct button styling', () => {
      renderComponent(0);

      const button = screen.getByRole('button', { name: /view audit logs/i });
      expect(button).toHaveClass(
        'px-4',
        'py-2',
        'text-sm',
        'font-medium',
        'text-blue-600',
        'hover:text-blue-700',
        'hover:bg-blue-50',
        'rounded-md',
        'transition-colors'
      );
    });
  });

  describe('Accessibility', () => {
    it('should have accessible button', () => {
      renderComponent(5);

      const button = screen.getByRole('button', { name: /view audit logs/i });
      expect(button).toBeInTheDocument();
      expect(button).toBeEnabled();
    });

    it('should have proper heading structure', () => {
      renderComponent(0);

      const heading = screen.getByText('Recent Errors (24h)');
      expect(heading).toHaveClass('text-xl', 'font-semibold');
    });
  });
});
