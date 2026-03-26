import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, RowData } from '../../types';
import styles from './index.module.css';

export interface CellRendererProps {
  value: any;
  column: ColumnConfig;
  rowData: RowData;
  isEditing?: boolean;
  onClick?: () => void;
  children?: React.ReactNode;
}

/**
 * Base CellRenderer component
 * 
 * Provides:
 * - Theme integration via useTheme hook
 * - Cell style application from column config
 * - Tooltip for truncated content
 * - Base styling and layout
 * 
 * Requirements: 1.6, 18.1, 18.2, 18.5
 */
export const CellRenderer: React.FC<CellRendererProps> = ({
  value,
  column,
  rowData,
  isEditing = false,
  onClick,
  children,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [showTooltip, setShowTooltip] = useState(false);

  // Apply custom cell style from column config if provided
  const customStyle = column.cellStyle 
    ? (column.cellStyle as (val: any, row: RowData) => React.CSSProperties)(value, rowData) 
    : {};

  // Base cell styles using theme tokens
  const baseStyle: React.CSSProperties = {
    borderBottom: `1px solid ${t.border}`,
    borderRight: `1px solid ${t.border}`,
    backgroundColor: isEditing ? t.bgInputFocus : t.bgCard,
    color: t.text,
    cursor: column.editable && !isEditing ? 'pointer' : 'default',
    ...customStyle, // Custom styles override base styles
  };

  const hoverStyle: React.CSSProperties = {
    backgroundColor: !isEditing && column.editable ? t.bgCardHover : baseStyle.backgroundColor,
  };

  // Determine if content is truncated (for tooltip)
  const isTruncated = typeof value === 'string' && value.length > 50;

  return (
    <div
      className={styles.cell}
      style={baseStyle}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (!isEditing && column.editable) {
          Object.assign(e.currentTarget.style, hoverStyle);
        }
        if (isTruncated) {
          setShowTooltip(true);
        }
      }}
      onMouseLeave={(e) => {
        Object.assign(e.currentTarget.style, { backgroundColor: baseStyle.backgroundColor });
        setShowTooltip(false);
      }}
      role="cell"
      aria-label={`${column.label}: ${value}`}
    >
      {children || value}
      
      {/* Tooltip for truncated content */}
      {showTooltip && isTruncated && (
        <div
          className={styles.tooltip}
          style={{
            backgroundColor: t.bgCard,
            border: `1px solid ${t.border}`,
            color: t.text,
          }}
        >
          {value}
        </div>
      )}
    </div>
  );
};
