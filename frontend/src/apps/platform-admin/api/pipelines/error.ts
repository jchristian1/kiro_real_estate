/**
 * Pipeline error helper — delegates to the shared getFriendlyErrorMessage
 * which covers all HTTP status codes with detailed messages.
 */

import { getFriendlyErrorMessage } from '@/shared/api/client';

export const getPipelineErrorMessage = getFriendlyErrorMessage;