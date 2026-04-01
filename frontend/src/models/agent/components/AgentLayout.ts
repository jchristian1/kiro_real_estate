export const PAGE_TITLES: Record<string, string> = {
  '/agent/dashboard': 'Dashboard',
  '/agent/leads': 'Leads',
  '/agent/settings': 'Settings',
  '/agent/reports': 'Reports',
};

export interface NavItem {
  to: string;
  label: string;
  icon: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/agent/dashboard', label: 'Dashboard', icon: '◈' },
  { to: '/agent/leads', label: 'Leads', icon: '◎' },
  { to: '/agent/settings', label: 'Settings', icon: '⚙' },
  { to: '/agent/reports', label: 'Reports', icon: '≡' },
];


