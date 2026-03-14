/**
 * API utility — friendly error messages and axios interceptor setup.
 * Requirements: 22.5, 22.6
 */
import axios, { AxiosError } from 'axios';

/** Map HTTP status codes to user-friendly messages */
export const getFriendlyErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string; message?: string }>;
    const status = axiosError.response?.status;
    const serverMsg =
      axiosError.response?.data?.detail ||
      axiosError.response?.data?.message;

    switch (status) {
      case 400:
        return serverMsg || 'Invalid request. Please check your input and try again.';
      case 401:
        return 'Your session has expired. Please log in again.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return serverMsg || 'The requested resource was not found.';
      case 409:
        return serverMsg || 'A conflict occurred. The resource may already exist.';
      case 422:
        return serverMsg || 'Validation failed. Please check your input.';
      case 429:
        return 'Too many requests. Please wait a moment and try again.';
      case 500:
        return 'An internal server error occurred. Please try again later or check the audit logs.';
      case 502:
      case 503:
      case 504:
        return 'The server is temporarily unavailable. Please try again later.';
      default:
        if (!axiosError.response) {
          return 'Unable to connect to the server. Please check your network connection.';
        }
        return serverMsg || `Unexpected error (${status}). Please try again.`;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred. Please try again.';
};
