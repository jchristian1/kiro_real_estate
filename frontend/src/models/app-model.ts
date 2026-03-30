export interface NavItem { to: string; label: string; icon: string; }
export interface NavGroup { label: string; items: NavItem[]; }

export interface Template {
  id: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface PreviewResult { subject: string; body: string; }

export interface TemplateVersion {
  version: number;
  name: string;
  subject: string;
  is_active: boolean;
  body: string;
  created_at: string;
  created_by: number;
}

export interface TemplateVersionConfirmDialog {
  id: number;
  version_number: number;
  is_active: boolean;
  published_at: string | null;
  subject_template: string;
}