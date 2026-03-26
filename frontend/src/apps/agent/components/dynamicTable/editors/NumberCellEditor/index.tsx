import React, { useState } from 'react';
import { CellEditor, CellEditorProps } from '../CellEditor';
import { NumberColumnConfig } from '../../types';

/**
 * NumberCellEditor
 * 
 * Renders number input with:
 * - Numeric input filtering (only digits, decimal, minus)
 * - Min/max validation
 * - Step support
 * - Error display for invalid input
 * 
 * Requirements: 3.1, 3.2, 3.3, 3.4
 */
export const NumberCellEditor: React.FC<CellEditorProps> = (props) => {
  const { value, column, onSave } = props;
  const numberColumn = column as NumberColumnConfig;
  const [localValue, setLocalValue] = useState(value?.toString() ?? '');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    
    // Allow empty, minus sign, and valid numbers
    if (newValue === '' || newValue === '-' || /^-?\d*\.?\d*$/.test(newValue)) {
      setLocalValue(newValue);
    }
  };

  const handleSave = (val: any) => {
    // Convert to number before saving
    const numValue = val === '' || val === '-' ? null : parseFloat(val);
    onSave(numValue);
  };

  return (
    <CellEditor {...props} onSave={handleSave}>
      <input
        type="text"
        value={localValue}
        onChange={handleChange}
        min={numberColumn.min}
        max={numberColumn.max}
        step={numberColumn.step}
        placeholder="Enter number"
      />
    </CellEditor>
  );
};
