import React, { useState } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, RowData, RowAction } from '../../types';
import { TableCell } from '../TableCell';
import styles from './index.module.css';

export interface TableRowProps {
  rowData: RowData;
  columns: ColumnConfig[];
  selectable?: boolean;
  isSelected?: boolean;
  onSelectionChange?: (selected: boolean) => void;
  onCellChange: (columnId: string, newValue: any) => void;
  rowActions?: RowAction[];
  onRowClick?: (rowData: RowData) => void;
}

/**
 * TableRow component
 * 
 * Renders a single table row with:
 * - Optional selection cell (checkbox)
 * - Data cells for each column
 * - Optional actions cell (menu)
 * - Row-level styling and hover effects
 * - Click event handling
 * 
 * Requirements: 14.1, 15.1
 */
export const TableRow: React.FC<TableRowProps> = ({
  rowData,
  columns,
  selectable = false,
  isSelected = false,
  onSelectionChange,
  onCellChange,
  rowActions,
  onRowClick,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [editingCellId, setEditingCellId] = useState<string | null>(null);

  // Handle row click
  const handleRowClick = () => {
    if (onRowClick) {
      onRowClick(rowData);
    }
  };

  // Handle selection change
  const handleSelectionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (onSelectionChange) {
      onSelectionChange(e.target.checked);
    }
  };

  // Handle cell value change
  const handleCellChange = (columnId: string, newValue: any) => {
    onCellChange(columnId, newValue);
    setEditingCellId(null);
  };

  // Handle actions menu click
  const handleActionsClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Actions menu will be implemented later
  };

  return (
    <div
      className={styles.row}
      style={{
        '--row-hover-bg': t.bgCardHover,
        backgroundColor: isSelected ? t.accentBg : 'transparent',
        borderBottom: `1px solid ${t.border}`,
      } as React.CSSProperties}
      onClick={handleRowClick}
      role="row"
      aria-selected={isSelected}
    >
      {/* Selection cell */}
      {selectable && (
        <div
          className={styles.selectionCell}
          style={{
            borderRight: `1px solid ${t.border}`,
          }}
          role="gridcell"
        >
          <input
            type="checkbox"
            className={styles.checkbox}
            checked={isSelected}
            onChange={handleSelectionChange}
            style={{
              accentColor: t.accent,
            }}
            aria-label="Select row"
          />
        </div>
      )}

      {/* Data cells */}
      {columns.map((column) => (
        <TableCell
          key={column.id}
          column={column}
          rowData={rowData}
          value={rowData[column.id]}
          onCellChange={(newValue) => handleCellChange(column.id, newValue)}
          isEditing={editingCellId === column.id}
          onEditStart={() => setEditingCellId(column.id)}
          onEditEnd={() => setEditingCellId(null)}
        />
      ))}

      {/* Actions cell */}
      {rowActions && rowActions.length > 0 && (
        <div
          className={styles.actionsCell}
          style={{
            borderLeft: `1px solid ${t.border}`,
          }}
          role="gridcell"
        >
          <button
            onClick={handleActionsClick}
            style={{
              padding: '4px 8px',
              backgroundColor: 'transparent',
              border: `1px solid ${t.border}`,
              borderRadius: '4px',
              color: t.text,
              cursor: 'pointer',
              fontSize: '14px',
            }}
            aria-label="Row actions"
          >
            ⋮
          </button>
        </div>
      )}
    </div>
  );
};
