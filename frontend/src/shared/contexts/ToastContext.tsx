/**
 * Toast Notification Context
 * 
 * Provides toast notification functionality for the application.
 * - Success toasts auto-dismiss after 3 seconds
 * - Error toasts require manual dismissal
 * - Toasts are displayed in a consistent location (top-right)
 * 
 * Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  autoDismiss: boolean;
}

interface ToastContextState {
  toasts: Toast[];
  showToast: (type: ToastType, message: string, autoDismiss?: boolean) => void;
  dismissToast: (id: string) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

const ToastContext = createContext<ToastContextState | undefined>(undefined);

interface ToastProviderProps {
  children: ReactNode;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  /**
   * Show a toast notification
   */
  const showToast = useCallback((type: ToastType, message: string, autoDismiss = true) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    const toast: Toast = { id, type, message, autoDismiss };

    setToasts((prev) => [...prev, toast]);

    // Auto-dismiss after 3 seconds for success toasts
    if (autoDismiss) {
      setTimeout(() => {
        dismissToast(id);
      }, 3000);
    }
  }, []);

  /**
   * Dismiss a toast notification
   */
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  /**
   * Convenience methods for different toast types
   */
  const success = useCallback((message: string) => {
    showToast('success', message, true);
  }, [showToast]);

  const error = useCallback((message: string) => {
    showToast('error', message, false);
  }, [showToast]);

  const info = useCallback((message: string) => {
    showToast('info', message, true);
  }, [showToast]);

  const warning = useCallback((message: string) => {
    showToast('warning', message, true);
  }, [showToast]);

  const value: ToastContextState = {
    toasts,
    showToast,
    dismissToast,
    success,
    error,
    info,
    warning,
  };

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
};

/**
 * Custom hook to use toast notifications
 */
// eslint-disable-next-line react-refresh/only-export-components
export const useToast = (): ToastContextState => {
  const context = useContext(ToastContext);
  
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  
  return context;
};
