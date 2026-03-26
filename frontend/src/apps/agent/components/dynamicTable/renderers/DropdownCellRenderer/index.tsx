import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import { DropdownColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * DropdownCellRenderer
 * 
 * Renders dropdown values with:
 * - Display of option label (not value)
 * - Badge-style pill for visual distinction
 * - Theme-integrated styling
 * 
 * Requirements: 4.1, 4.5
 */
export const DropdownCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value, column } = props;
  const { theme } = useTheme();
  const t = getTokens(theme);
  const dropdownColumn = column as DropdownColumnConfig;
  
  // Handle null/undefined
  if (value === null || value === undefined || value === '') {
    return <CellRenderer {...props}>—</CellRenderer>;
  }
  
  // Find the label for the value
  let displayLabel = value;
  
  if (dropdownColumn.options) {
    const option = dropdownColumn.options.find(opt => 
      typeof opt === 'string' ? opt === value : opt.value === value
    );
    
    if (option) {
      displayLabel = typeof option === 'string' ? option : option.label;
    }
  }
  
  return (
    <CellRenderer {...props}>
      <span
        className={styles.badge}
        style={{
          backgroundColor: t.bgBadge,
          color: t.text,
        }}
      >
        {displayLabel}
      </span>
    </CellRenderer>
  );
};
