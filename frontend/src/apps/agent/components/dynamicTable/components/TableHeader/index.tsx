import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, SortState, RowAction } from '../../types';
import { ColumnHeader } from '../ColumnHeader';
import styles from './index.module.css';

export interface TableHeaderProps {
  columns: ColumnConfig[];
  selectable?: boolean;
  allSelected?: boolean;
  someSelected?: boolean;
  onSelectAll?: (selected: boolean) => void;
  sortState?: SortState | null;
  onSortChange?: (columnId: string) => void;
  onFilterClick?: (columnId: string) => void;
  activeFilters?: Set<string>;
  allowReorder?: boolean;
  onColumnDragStart?: (columnId: string) => void;
  rowActions?: RowAction[];
}

/**
 * TableHeader component
 * 
 * Renders the table header row with:
 * - Optional selection header cell (bulk select checkbox)
 * - Column headers for all visible columns
 * - Optional actions header cell
 * - Theme-integrated styling
 * 
 * Requirements: 14.1, 15.1, 18.1
 */
export const TableHeader: React.FC<TableHeaderProps> = ({
  columns,
  selectable = false,
  allSelected = false,
  someSelected = false,
  onSelectAll,
  sortState,
  onSortChange,
  onFilterClick,
  activeFilters = new Set(),
  allowReorder = false,
  onColumnDragStart,
  rowActions,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  // Handle select all change
  const handleSelectAllChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (onSelectAll) {
      onSelectAll(e.target.checked);
    }
  };

  return (
    <div
      className={styles.header}
      style={{
        backgroundColor: t.bgCard,
        borderBottom: `2px solid ${t.border}`,
      }}
      role="row"
    >
      {/* Selection header cell */}
      {selectable && (
        <div
          className={styles.selectionHeaderCell}
          style={{
            backgroundColor: t.bgCard,
            borderRight: `1px solid ${t.border}`,
            borderBottom: `2px solid ${t.border}`,
            color: t.text,
          }}
          role="columnheader"
        >
          <input
            type="checkbox"
            className={styles.checkbox}
            checked={allSelected}
            ref={(input) => {
              if (input) {
                input.indeterminate = someSelected && !allSelected;
              }
            }}
            onChange={handleSelectAllChange}
            style={{
              accentColor: t.accent,
            }}
            aria-label="Select all rows"
          />
        </div>
      )}

      {/* Column headers */}
      {columns.map((column) => (
        <ColumnHeader
          key={column.id}
          column={column}
          sortState={sortState}
          onSortChange={onSortChange}
          onFilterClick={onFilterClick}
          hasActiveFilter={activeFilters.has(column.id)}
          allowReorder={allowReorder}
          onDragStart={onColumnDragStart}
        />
      ))}

      {/* Actions header cell */}
      {rowActions && rowActions.length > 0 && (
        <div
          className={styles.actionsHeaderCell}
          style={{
            backgroundColor: t.bgCard,
            borderLeft: `1px solid ${t.border}`,
            borderBottom: `2px solid ${t.border}`,
            color: t.text,
          }}
          role="columnheader"
        >
          Actions
        </div>
      )}
    </div>
  );
};
