import { z } from "zod";

const isValidRegex = (val: string) => { try { new RegExp(val); return true; } catch { return false; } };

export const leadSourceSchema = z.object({
  sender_email: z.string().min(1, 'Sender email is required').email('Invalid email address'),
  identifier_snippet: z.string().min(1, 'Identifier snippet is required'),
  name_regex: z.string().min(1, 'Name regex is required').refine(isValidRegex, 'Invalid regex syntax'),
  phone_regex: z.string().min(1, 'Phone regex is required').refine(isValidRegex, 'Invalid regex syntax'),
  template_id: z.number().nullable().optional(),
  auto_respond_enabled: z.boolean(),
});



export const templateSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  subject: z.string().min(1, 'Subject is required').max(500)
    .refine((v) => !v.includes('\n') && !v.includes('\r'), 'Subject cannot contain newlines'),
  body: z.string().min(1, 'Body is required'),
});

export type TemplateFormValues = z.infer<typeof templateSchema>;