export interface Company { id: number; name: string; }


export interface AgentDetailData {
  id: number;
  agent_id: string;
  email: string;
  display_name: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentTemplate {
  id?: number;
  type: string; label: string; name: string; subject: string; body: string;
  is_custom: boolean; is_active: boolean; version: number;
}

