import React, { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellEditorProps } from '../CellEditor';
import { DateColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * DateCellEditor
 * 
 * Renders date picker with:
 * - ISO 8601 format persistence
 * - Min/max date validation
 * - Keyboard navigation
 * - Native date input with custom styling
 * 
 * Requirements: 7.1, 7.2, 7.4, 7.5
 */
export const DateCellEditor: React.FC<CellEditorProps> = ({
  value: initialValue,
  column,
  onSave,
  onCancel,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const dateColumn = column as DateColumnConfig;
  
  // Parse initial value to date string for input
  let initialDateString = '';
  if (initialValue) {
    try {
      const date = typeof initialValue === 'string' ? parseISO(initialValue) : new Date(initialValue);
      initialDateString = format(date, 'yyyy-MM-dd');
    } catch {
      initialDateString = '';
    }
  }
  
  const [value, setValue] = useState(initialDateString);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSave(value);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  };

  const handleBlur = () => {
    onSave(value);
  };

  // Format min/max dates for input
  const minDateStr = dateColumn.minDate ? format(dateColumn.minDate, 'yyyy-MM-dd') : undefined;
  const maxDateStr = dateColumn.maxDate ? format(dateColumn.maxDate, 'yyyy-MM-dd') : undefined;

  return (
    <div
      className={styles.container}
      style={{
        borderBottom: `1px solid ${t.border}`,
        borderRight: `1px solid ${t.border}`,
        backgroundColor: t.bgInputFocus,
      }}
    >
      <input
        type="date"
        className={styles.dateInput}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        min={minDateStr}
        max={maxDateStr}
        autoFocus
        style={{
          backgroundColor: t.bgInput,
          border: `1px solid ${t.borderFocus}`,
          color: t.text,
        }}
      />
    </div>
  );
};
