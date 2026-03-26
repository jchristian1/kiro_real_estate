import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import { ButtonColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * ButtonCellRenderer
 * 
 * Renders button with:
 * - Variant styling (primary, secondary, danger, ghost)
 * - Icon support
 * - Disabled state
 * - onClick callback execution
 * - Theme-integrated styling
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4
 */
export const ButtonCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { column, rowData } = props;
  const { theme } = useTheme();
  const t = getTokens(theme);
  const buttonColumn = column as ButtonColumnConfig;
  
  // Determine if button should be disabled
  const isDisabled = buttonColumn.buttonDisabled ? buttonColumn.buttonDisabled(rowData) : false;
  
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isDisabled && buttonColumn.onClick) {
      buttonColumn.onClick(rowData);
    }
  };
  
  // Get button styles based on variant
  const getButtonStyles = (): React.CSSProperties => {
    switch (buttonColumn.buttonVariant) {
      case 'primary':
        return {
          backgroundColor: t.accent,
          color: '#ffffff',
        };
      case 'danger':
        return {
          backgroundColor: t.red,
          color: '#ffffff',
        };
      case 'ghost':
        return {
          backgroundColor: 'transparent',
          color: t.text,
          border: `1px solid ${t.border}`,
        };
      case 'secondary':
      default:
        return {
          backgroundColor: t.bgBadge,
          color: t.text,
        };
    }
  };
  
  return (
    <CellRenderer {...props} onClick={undefined}>
      <button
        className={styles.button}
        onClick={handleClick}
        disabled={isDisabled}
        style={getButtonStyles()}
        aria-label={buttonColumn.buttonLabel}
      >
        {buttonColumn.buttonIcon && (
          <span>{buttonColumn.buttonIcon}</span>
        )}
        {buttonColumn.buttonLabel}
      </button>
    </CellRenderer>
  );
};
