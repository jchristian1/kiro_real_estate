import { leadSourceSchema } from "@/shared/utils";
import { z } from "zod";

export interface LeadSource {
  id: number;
  sender_email: string;
  identifier_snippet: string;
  name_regex: string;
  phone_regex: string;
  template_id: number | null;
  auto_respond_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface Template { id: number; name: string; }

export type LeadSourceFormValues = z.infer<typeof leadSourceSchema>;
