import React from 'react';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import { NumberColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * NumberCellRenderer
 * 
 * Renders numbers with:
 * - Formatting based on column config (currency, percentage, decimal)
 * - Right-alignment by default
 * - Proper decimal places
 * - Theme-integrated styling
 * 
 * Requirements: 3.1, 3.5
 */
export const NumberCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value, column } = props;
  const numberColumn = column as NumberColumnConfig;
  
  // Handle null/undefined
  if (value === null || value === undefined || value === '') {
    return <CellRenderer {...props}>—</CellRenderer>;
  }
  
  const numValue = typeof value === 'number' ? value : parseFloat(value);
  
  // Handle invalid numbers
  if (isNaN(numValue)) {
    return <CellRenderer {...props}>Invalid</CellRenderer>;
  }
  
  // Format based on column config
  let formattedValue: string;
  
  switch (numberColumn.format) {
    case 'currency':
      formattedValue = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: numberColumn.decimalPlaces ?? 2,
        maximumFractionDigits: numberColumn.decimalPlaces ?? 2,
      }).format(numValue);
      break;
      
    case 'percentage':
      formattedValue = new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: numberColumn.decimalPlaces ?? 0,
        maximumFractionDigits: numberColumn.decimalPlaces ?? 2,
      }).format(numValue / 100);
      break;
      
    case 'decimal':
      formattedValue = new Intl.NumberFormat('en-US', {
        minimumFractionDigits: numberColumn.decimalPlaces ?? 0,
        maximumFractionDigits: numberColumn.decimalPlaces ?? 2,
      }).format(numValue);
      break;
      
    default:
      // Default formatting
      formattedValue = new Intl.NumberFormat('en-US', {
        maximumFractionDigits: numberColumn.decimalPlaces ?? 2,
      }).format(numValue);
  }
  
  return (
    <CellRenderer {...props}>
      <span className={styles.numberContent}>
        {formattedValue}
      </span>
    </CellRenderer>
  );
};
