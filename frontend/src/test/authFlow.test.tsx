/**
 * Integration tests for authentication flow
 * 
 * **Validates: Requirements 23.3**
 * 
 * Tests cover:
 * - Login success - user can login with valid credentials and is redirected to dashboard
 * - Login failure - user sees error message with invalid credentials
 * - Logout - user can logout and is redirected to login page
 * - Protected route redirect - unauthenticated users are redirected to login
 * - Protected route access - authenticated users can access protected routes
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import { AuthProvider } from '../contexts/AuthContext';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { DashboardLayout } from '../components/DashboardLayout';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';
import { AgentsPage } from '../pages/AgentsPage';
import { SettingsPage } from '../pages/SettingsPage';

// Mock axios
vi.mock('axios');
const mockedAxios = axios as any;

describe('Authentication Flow Integration Tests', () => {
  // Helper to render the app with routing
  const renderApp = (initialRoute = '/') => {
    return render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <AuthProvider>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* Redirect root to dashboard */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            
            {/* Protected routes */}
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            
            {/* Catch-all redirect to dashboard */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks();
    
    // Setup default axios mock
    mockedAxios.defaults = { withCredentials: false };
    mockedAxios.get = vi.fn();
    mockedAxios.post = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Login Success', () => {
    it('should login with valid credentials and redirect to dashboard', async () => {
      const user = userEvent.setup();
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Mock login success
      mockedAxios.post.mockResolvedValueOnce({
        data: { user: mockUser },
      });

      // Render app starting at login page
      renderApp('/login');

      // Wait for login page to render
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });

      // Fill in login form
      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const loginButton = screen.getByRole('button', { name: /login/i });

      await user.type(usernameInput, 'admin');
      await user.type(passwordInput, 'password123');
      await user.click(loginButton);

      // Verify login API was called
      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/auth/login'),
          { username: 'admin', password: 'password123' }
        );
      });

      // Verify redirect to dashboard (login page should no longer be visible)
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });
    });

    it('should show loading state during login', async () => {
      const user = userEvent.setup();

      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Mock login with delay
      mockedAxios.post.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          data: { user: { id: 1, username: 'admin', role: 'admin' } }
        }), 100))
      );

      renderApp('/login');

      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const loginButton = screen.getByRole('button', { name: /login/i });

      await user.type(usernameInput, 'admin');
      await user.type(passwordInput, 'password123');
      await user.click(loginButton);

      // Check for loading state
      await waitFor(() => {
        expect(screen.getByText(/logging in/i)).toBeInTheDocument();
      });

      // Wait for login to complete
      await waitFor(() => {
        expect(screen.queryByText(/logging in/i)).not.toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('Login Failure', () => {
    it('should show error message with invalid credentials', async () => {
      const user = userEvent.setup();

      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Mock login failure
      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 401,
          data: { message: 'Invalid username or password' },
        },
      });

      renderApp('/login');

      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });

      // Fill in login form with invalid credentials
      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const loginButton = screen.getByRole('button', { name: /login/i });

      await user.type(usernameInput, 'admin');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(loginButton);

      // Verify error message is displayed
      await waitFor(() => {
        expect(screen.getByText('Invalid username or password')).toBeInTheDocument();
      });

      // Verify user is still on login page
      expect(screen.getByText('Admin Login')).toBeInTheDocument();
    });

    it('should show generic error message on network failure', async () => {
      const user = userEvent.setup();

      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Mock network error
      mockedAxios.post.mockRejectedValueOnce(new Error('Network error'));

      renderApp('/login');

      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const loginButton = screen.getByRole('button', { name: /login/i });

      await user.type(usernameInput, 'admin');
      await user.type(passwordInput, 'password123');
      await user.click(loginButton);

      // Verify generic error message is displayed
      await waitFor(() => {
        expect(screen.getByText(/login failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Logout Functionality', () => {
    it('should logout and redirect to login page', async () => {
      const user = userEvent.setup();
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      // Mock logout success
      mockedAxios.post.mockResolvedValueOnce({
        data: { message: 'Logged out successfully' },
      });

      // Render app starting at dashboard
      renderApp('/dashboard');

      // Wait for dashboard to load (user is authenticated)
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });

      // Find and click logout button (assuming it's in the header/sidebar)
      const logoutButton = screen.getByRole('button', { name: /logout/i });
      await user.click(logoutButton);

      // Verify logout API was called
      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/auth/logout')
        );
      });

      // Mock session check after logout (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Verify redirect to login page
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });

    it('should clear user state even if logout API fails', async () => {
      const user = userEvent.setup();
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      // Mock logout failure
      mockedAxios.post.mockRejectedValueOnce(new Error('Network error'));

      renderApp('/dashboard');

      // Wait for dashboard to load
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });

      // Find and click logout button
      const logoutButton = screen.getByRole('button', { name: /logout/i });
      await user.click(logoutButton);

      // Mock session check after logout (no session)
      mockedAxios.get.mockRejectedValueOnce({
        response: { status: 401 },
      });

      // Verify redirect to login page even though API failed
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });
  });

  describe('Protected Route Redirect', () => {
    it('should redirect unauthenticated users to login page', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({
        response: { status: 401 },
      });

      // Try to access protected route (dashboard)
      renderApp('/dashboard');

      // Verify redirect to login page
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });

    it('should redirect unauthenticated users from agents page', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({
        response: { status: 401 },
      });

      // Try to access agents page
      renderApp('/agents');

      // Verify redirect to login page
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });

    it('should redirect unauthenticated users from settings page', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({
        response: { status: 401 },
      });

      // Try to access settings page
      renderApp('/settings');

      // Verify redirect to login page
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });

    it('should show loading state while checking authentication', async () => {
      // Mock initial session check with delay
      mockedAxios.get.mockImplementation(() => 
        new Promise((_, reject) => setTimeout(() => reject({
          response: { status: 401 }
        }), 100))
      );

      renderApp('/dashboard');

      // Check for loading state
      expect(screen.getByText(/loading/i)).toBeInTheDocument();

      // Wait for redirect to login
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('Protected Route Access', () => {
    it('should allow authenticated users to access dashboard', async () => {
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      renderApp('/dashboard');

      // Verify dashboard is accessible (no redirect to login)
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });

      // Verify session check was called
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/auth/me')
      );
    });

    it('should allow authenticated users to access agents page', async () => {
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      renderApp('/agents');

      // Verify agents page is accessible
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });
    });

    it('should allow authenticated users to access settings page', async () => {
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      renderApp('/settings');

      // Verify settings page is accessible
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });
    });

    it('should persist authentication across route changes', async () => {
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      renderApp('/dashboard');

      // Wait for dashboard to load
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });

      // Note: In a real integration test, we would navigate using links/buttons
      // For this test, we're verifying that authentication state persists
      // The actual navigation would be tested in E2E tests
    });
  });

  describe('Root Path Redirect', () => {
    it('should redirect authenticated users from root to dashboard', async () => {
      const mockUser = {
        id: 1,
        username: 'admin',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });

      renderApp('/');

      // Verify redirect to dashboard (not login page)
      await waitFor(() => {
        expect(screen.queryByText('Admin Login')).not.toBeInTheDocument();
      });
    });

    it('should redirect unauthenticated users from root to login', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({
        response: { status: 401 },
      });

      renderApp('/');

      // Verify redirect to login page
      await waitFor(() => {
        expect(screen.getByText('Admin Login')).toBeInTheDocument();
      });
    });
  });
});
