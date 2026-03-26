import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import { CheckboxColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * CheckboxCellRenderer
 * 
 * Renders checkbox with:
 * - Boolean value display
 * - Indeterminate state for null/undefined
 * - Immediate toggle on click (no explicit edit mode)
 * - Disabled state support
 * - Theme-integrated styling
 * 
 * Requirements: 5.1, 5.2, 5.5
 */
export const CheckboxCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value, column, rowData, onClick } = props;
  const { theme } = useTheme();
  const t = getTokens(theme);
  const checkboxColumn = column as CheckboxColumnConfig;
  
  // Determine if checkbox should be disabled
  const isDisabled = checkboxColumn.disabled ? checkboxColumn.disabled(rowData) : false;
  
  // Determine checkbox state
  const isChecked = value === true;
  const isIndeterminate = value === null || value === undefined;
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (!isDisabled && onClick) {
      onClick();
    }
  };
  
  const handleClick = (e: React.MouseEvent<HTMLInputElement>) => {
    e.stopPropagation();
  };
  
  return (
    <CellRenderer {...props} onClick={undefined}>
      <div className={styles.checkboxContainer}>
        <input
          type="checkbox"
          className={styles.checkbox}
          checked={isChecked}
          ref={(input) => {
            if (input) {
              input.indeterminate = isIndeterminate;
            }
          }}
          disabled={isDisabled}
          onChange={handleChange}
          onClick={handleClick}
          style={{
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            accentColor: t.accent,
            opacity: isDisabled ? 0.5 : 1,
          }}
          aria-label={`${column.label} checkbox`}
        />
      </div>
    </CellRenderer>
  );
};
