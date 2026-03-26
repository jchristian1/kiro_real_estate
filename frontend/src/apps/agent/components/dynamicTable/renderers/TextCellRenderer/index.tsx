import React from 'react';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import styles from './index.module.css';

/**
 * TextCellRenderer
 * 
 * Renders plain text with:
 * - Ellipsis truncation for long text
 * - Hover tooltip showing full text (inherited from CellRenderer)
 * - Theme-integrated styling
 * 
 * Requirements: 2.1
 */
export const TextCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value } = props;
  
  // Display empty string for null/undefined
  const displayValue = value ?? '';
  
  return (
    <CellRenderer {...props}>
      <span className={styles.textContent}>
        {displayValue}
      </span>
    </CellRenderer>
  );
};
