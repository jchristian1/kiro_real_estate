import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, RowData } from '../../types';
import { 
  TextCellRenderer, 
  NumberCellRenderer, 
  DropdownCellRenderer, 
  CheckboxCellRenderer, 
  ButtonCellRenderer, 
  DateCellRenderer, 
  LongTextCellRenderer, 
  ColorCellRenderer 
} from '../../renderers';
import { 
  TextCellEditor, 
  NumberCellEditor, 
  DropdownCellEditor, 
  DateCellEditor, 
  LongTextCellEditor, 
  ColorCellEditor 
} from '../../editors';
import styles from './index.module.css';

export interface TableCellProps {
  column: ColumnConfig;
  rowData: RowData;
  value: any;
  onCellChange: (newValue: any) => void;
  isEditing?: boolean;
  onEditStart?: () => void;
  onEditEnd?: () => void;
}

/**
 * TableCell component
 * 
 * Manages the cell container and toggles between renderer and editor modes.
 * 
 * Features:
 * - Click to activate edit mode (if editable)
 * - Renders appropriate renderer/editor based on column type
 * - Handles focus management
 * - Respects editable flag from column config
 * 
 * Requirements: 10.1, 10.2, 10.6
 */
export const TableCell: React.FC<TableCellProps> = ({
  column,
  rowData,
  value,
  onCellChange,
  isEditing = false,
  onEditStart,
  onEditEnd,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  // Handle click to enter edit mode
  const handleClick = () => {
    if (column.editable && !isEditing && column.type !== 'button' && column.type !== 'checkbox') {
      onEditStart?.();
    }
  };

  // Handle save from editor
  const handleSave = (newValue: any) => {
    onCellChange(newValue);
    onEditEnd?.();
  };

  // Handle cancel from editor
  const handleCancel = () => {
    onEditEnd?.();
  };

  // Handle checkbox immediate toggle
  const handleCheckboxToggle = () => {
    const newValue = !value;
    onCellChange(newValue);
  };

  // Get the appropriate renderer component
  const getRenderer = () => {
    const rendererProps = {
      value,
      column,
      rowData,
      onClick: handleClick,
    };

    switch (column.type) {
      case 'text':
        return <TextCellRenderer {...rendererProps} />;
      case 'number':
        return <NumberCellRenderer {...rendererProps} />;
      case 'dropdown':
        return <DropdownCellRenderer {...rendererProps} />;
      case 'checkbox':
        return <CheckboxCellRenderer {...rendererProps} onClick={handleCheckboxToggle} />;
      case 'button':
        return <ButtonCellRenderer {...rendererProps} />;
      case 'date':
        return <DateCellRenderer {...rendererProps} />;
      case 'longtext':
        return <LongTextCellRenderer {...rendererProps} />;
      case 'color':
        return <ColorCellRenderer {...rendererProps} />;
      default:
        return <TextCellRenderer {...rendererProps} />;
    }
  };

  // Get the appropriate editor component
  const getEditor = () => {
    const editorProps = {
      value,
      column,
      rowData,
      onSave: handleSave,
      onCancel: handleCancel,
    };

    switch (column.type) {
      case 'text':
        return <TextCellEditor {...editorProps} />;
      case 'number':
        return <NumberCellEditor {...editorProps} />;
      case 'dropdown':
        return <DropdownCellEditor {...editorProps} />;
      case 'checkbox':
        // Checkboxes don't have a separate editor - they edit in place
        return getRenderer();
      case 'date':
        return <DateCellEditor {...editorProps} />;
      case 'longtext':
        return <LongTextCellEditor {...editorProps} />;
      case 'color':
        return <ColorCellEditor {...editorProps} />;
      default:
        return <TextCellEditor {...editorProps} />;
    }
  };

  return (
    <div
      className={styles.cell}
      style={{
        outlineColor: t.accent,
      }}
      role="gridcell"
      tabIndex={column.editable && !isEditing ? 0 : -1}
      aria-label={`${column.label}: ${value}`}
    >
      {isEditing ? getEditor() : getRenderer()}
    </div>
  );
};
