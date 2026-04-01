/**
 * BackendPendingBadge — consistent indicator for features not yet supported by the backend.
 * Use this everywhere instead of ad-hoc "SOON" / "Coming soon" labels.
 */

import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';


export interface BackendPendingBadgeProps {
  /** Short label shown inline. Defaults to "Soon" */
  label?: string;
  /** Tooltip text on hover */
  tooltip?: string;
  /** Render as a standalone pill (default) or inline text */
  variant?: 'pill' | 'inline';
}

export const BackendPendingBadge: React.FC<BackendPendingBadgeProps> = ({
  label = 'Soon',
  tooltip = 'Coming soon — not yet supported',
  variant = 'pill',
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [hovered, setHovered] = useState(false);

  if (variant === 'inline') {
    return (
      <span
        title={tooltip}
        style={{ fontSize: 10, color: t.textFaint, letterSpacing: '0.3px', fontWeight: 600 }}
      >
        {label.toUpperCase()}
      </span>
    );
  }

  return (
    <span
      title={tooltip}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
        padding: '2px 7px', borderRadius: 5,
        color: t.textFaint,
        background: hovered ? t.bgBadge : 'transparent',
        border: `1px dashed ${t.border}`,
        cursor: 'default', transition: 'background 0.15s',
        textTransform: 'uppercase',
        userSelect: 'none',
      }}
    >
      <span style={{ fontSize: 8 }}>◌</span>
      {label}
    </span>
  );
};
