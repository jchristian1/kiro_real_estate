import React from 'react';
import { CellEditor, CellEditorProps } from '../CellEditor';
import { TextColumnConfig } from '../../types';

/**
 * TextCellEditor
 * 
 * Renders text input with:
 * - maxLength constraint
 * - Validation and error display
 * - Keyboard handling (Enter, Escape, Tab)
 * 
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 */
export const TextCellEditor: React.FC<CellEditorProps> = (props) => {
  const { value, column } = props;
  const textColumn = column as TextColumnConfig;
  
  return (
    <CellEditor {...props}>
      <input
        type="text"
        defaultValue={value ?? ''}
        maxLength={textColumn.maxLength}
        placeholder={textColumn.placeholder}
      />
    </CellEditor>
  );
};
