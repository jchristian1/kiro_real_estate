/**
 * Unit tests for AuthContext
 * 
 * Tests cover:
 * - AuthProvider initialization
 * - Login success and failure
 * - Logout functionality
 * - Session persistence check
 * - Error handling
 * - useAuth hook validation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { ReactNode } from 'react';
import axios from 'axios';
import { AuthProvider, useAuth, User } from './AuthContext';

// Mock axios
vi.mock('axios');
const mockedAxios = axios as any;

// Helper to create wrapper with AuthProvider
const createWrapper = () => {
  return ({ children }: { children: ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );
};

describe('AuthContext', () => {
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

  describe('AuthProvider initialization', () => {
    it('should initialize with loading state', () => {
      mockedAxios.get.mockRejectedValue(new Error('No session'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      expect(result.current.loading).toBe(true);
      expect(result.current.user).toBe(null);
      expect(result.current.error).toBe(null);
    });

    it('should check for existing session on mount', async () => {
      const mockUser: User = {
        id: 1,
        username: 'testuser',
        role: 'admin',
      };

      mockedAxios.get.mockResolvedValue({ data: mockUser });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.error).toBe(null);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/auth/me')
      );
    });

    it('should handle no existing session', async () => {
      mockedAxios.get.mockRejectedValue({
        response: { status: 401 },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.user).toBe(null);
    });
  });

  describe('login', () => {
    it('should login successfully', async () => {
      const mockUser: User = {
        id: 1,
        username: 'testuser',
        role: 'admin',
      };

      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({ response: { status: 401 } });
      
      // Mock login success
      mockedAxios.post.mockResolvedValue({
        data: { user: mockUser },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Perform login
      await act(async () => {
        await result.current.login('testuser', 'password');
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.error).toBe(null);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/auth/login'),
        { username: 'testuser', password: 'password' }
      );
    });

    it('should handle login failure', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({ response: { status: 401 } });
      
      // Mock login failure
      mockedAxios.post.mockRejectedValue({
        response: {
          status: 401,
          data: { message: 'Invalid username or password' },
        },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Perform login and expect it to throw
      await expect(async () => {
        await act(async () => {
          await result.current.login('testuser', 'wrongpassword');
        });
      }).rejects.toThrow('Invalid username or password');

      expect(result.current.user).toBe(null);
      expect(result.current.error).toBe('Invalid username or password');
    });

    it('should handle network error during login', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({ response: { status: 401 } });
      
      // Mock network error
      mockedAxios.post.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Perform login and expect it to throw
      await expect(async () => {
        await act(async () => {
          await result.current.login('testuser', 'password');
        });
      }).rejects.toThrow('Login failed. Please try again.');

      expect(result.current.user).toBe(null);
      expect(result.current.error).toBe('Login failed. Please try again.');
    });
  });

  describe('logout', () => {
    it('should logout successfully', async () => {
      const mockUser: User = {
        id: 1,
        username: 'testuser',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });
      
      // Mock logout success
      mockedAxios.post.mockResolvedValue({
        data: { message: 'Logged out successfully' },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      // Perform logout
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBe(null);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/auth/logout')
      );
    });

    it('should clear user state even if logout fails', async () => {
      const mockUser: User = {
        id: 1,
        username: 'testuser',
        role: 'admin',
      };

      // Mock initial session check (has session)
      mockedAxios.get.mockResolvedValue({ data: mockUser });
      
      // Mock logout failure
      mockedAxios.post.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      // Perform logout - should not throw
      await act(async () => {
        await result.current.logout();
      });

      // User should still be cleared
      expect(result.current.user).toBe(null);
    });
  });

  describe('clearError', () => {
    it('should clear error message', async () => {
      // Mock initial session check (no session)
      mockedAxios.get.mockRejectedValue({ response: { status: 401 } });
      
      // Mock login failure
      mockedAxios.post.mockRejectedValue({
        response: {
          status: 401,
          data: { message: 'Invalid credentials' },
        },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Wait for initial loading to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Perform failed login
      await expect(async () => {
        await act(async () => {
          await result.current.login('testuser', 'wrongpassword');
        });
      }).rejects.toThrow();

      expect(result.current.error).toBe('Invalid credentials');

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBe(null);
    });
  });

  describe('useAuth hook', () => {
    it('should throw error when used outside AuthProvider', () => {
      // Suppress console.error for this test
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within an AuthProvider');

      consoleError.mockRestore();
    });
  });
});
