import React from 'react';
import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import { CellRenderer, CellRendererProps } from '../CellRenderer';
import { DateColumnConfig } from '../../types';

/**
 * DateCellRenderer
 * 
 * Renders dates with:
 * - Formatting based on column config
 * - Relative time in tooltip (e.g., "2 days ago")
 * - ISO 8601 format support
 * - Theme-integrated styling
 * 
 * Requirements: 7.1, 7.3
 */
export const DateCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value, column } = props;
  const dateColumn = column as DateColumnConfig;
  
  // Handle null/undefined
  if (value === null || value === undefined || value === '') {
    return <CellRenderer {...props}>—</CellRenderer>;
  }
  
  // Parse date
  let date: Date;
  try {
    date = typeof value === 'string' ? parseISO(value) : new Date(value);
  } catch {
    return <CellRenderer {...props}>Invalid Date</CellRenderer>;
  }
  
  // Validate date
  if (!isValid(date)) {
    return <CellRenderer {...props}>Invalid Date</CellRenderer>;
  }
  
  // Format date according to config (default: MM/DD/YYYY)
  const dateFormat = dateColumn.dateFormat || 'MM/dd/yyyy';
  const formattedDate = format(date, dateFormat);
  
  // Calculate relative time for tooltip
  const relativeTime = formatDistanceToNow(date, { addSuffix: true });
  
  return (
    <CellRenderer {...props}>
      <span title={relativeTime}>
        {formattedDate}
      </span>
    </CellRenderer>
  );
};
