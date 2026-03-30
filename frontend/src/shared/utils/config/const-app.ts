import { NavGroup } from "@/models/app-model";

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: '◈' },
      { to: '/leads', label: 'Leads', icon: '◎' },
      { to: '/leads-law', label: 'LeadsLaw', icon: '◎' },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { to: '/pipelines', label: 'Pipelines', icon: '⟶' },
      { to: '/templates', label: 'Templates', icon: '◧' },
      { to: '/forms', label: 'Forms', icon: '⊞' },
      { to: '/lead-sources', label: 'Lead Sources', icon: '⬡' },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/agents', label: 'Agents', icon: '◉' },
      { to: '/companies', label: 'Companies', icon: '▣' },
      { to: '/audit-logs', label: 'Audit Logs', icon: '≡' },
      { to: '/settings', label: 'Settings', icon: '⚙' },
    ],
  },
];

export const POLL_INTERVAL_MS = 5000;