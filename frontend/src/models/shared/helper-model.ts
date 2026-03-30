export interface RegexTestResult {
  matched: boolean;
  match_text: string | null;
  groups: string[];
  named_groups: Record<string, string>;
}

export interface RegexTestResponse {
  pattern: string;
  test_text: string;
  result: RegexTestResult;
}

export interface RegexProfileVersion {
  version: number;
  name_regex: string;
  phone_regex: string;
  identifier_snippet: string;
  created_at: string;
  created_by: number;
}