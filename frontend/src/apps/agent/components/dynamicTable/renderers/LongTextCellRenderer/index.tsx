import React from 'react';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import styles from './index.module.css';

/**
 * LongTextCellRenderer
 * 
 * Renders long text with:
 * - Truncation with ellipsis (2 lines max)
 * - Full text in tooltip on hover (inherited from CellRenderer)
 * - Theme-integrated styling
 * 
 * Requirements: 8.1, 8.5
 */
export const LongTextCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value } = props;
  
  // Display empty string for null/undefined
  const displayValue = value ?? '';
  
  return (
    <CellRenderer {...props}>
      <div className={styles.longTextContent}>
        {displayValue}
      </div>
    </CellRenderer>
  );
};
