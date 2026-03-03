/**
 * Tests for App routing structure
 * 
 * Requirements: 6.6, 23.3
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock AuthContext to avoid API calls in tests
vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({
    user: null,
    loading: false,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    clearError: vi.fn(),
  }),
}));

describe('App Routing', () => {
  it('renders without crashing', () => {
    render(<App />);
    // App should render successfully
    expect(document.body).toBeTruthy();
  });

  it('redirects to login when not authenticated', () => {
    render(<App />);
    // Should show login page when not authenticated
    expect(screen.getByText(/Admin Login/i)).toBeInTheDocument();
  });
});
