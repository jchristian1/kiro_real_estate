import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, RowData, RowAction } from '../../types';
import { TableRow } from '../TableRow';
import styles from './index.module.css';

export interface VirtualTableBodyProps {
  data: RowData[];
  columns: ColumnConfig[];
  selectable?: boolean;
  selectedRowIds?: Set<string>;
  onSelectionChange?: (rowId: string, selected: boolean) => void;
  onCellChange: (rowId: string, columnId: string, newValue: any) => void;
  onRowClick?: (rowData: RowData) => void;
  rowActions?: RowAction[];
  virtualScrolling?: boolean;
  maxHeight?: number;
}

/**
 * VirtualTableBody component
 * 
 * Renders the table body with optional virtual scrolling:
 * - Activates virtual scrolling for 100+ rows
 * - Renders only visible rows plus buffer
 * - Handles row selection and cell editing
 * - Displays empty state when no data
 * 
 * Requirements: 20.1
 */
export const VirtualTableBody: React.FC<VirtualTableBodyProps> = ({
  data,
  columns,
  selectable = false,
  selectedRowIds = new Set(),
  onSelectionChange,
  onCellChange,
  onRowClick,
  rowActions,
  virtualScrolling = true,
  maxHeight = 600,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const parentRef = useRef<HTMLDivElement>(null);

  // Determine if virtual scrolling should be active
  const shouldVirtualize = virtualScrolling && data.length >= 100;

  // Set up virtualizer
  const rowVirtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48, // Estimated row height
    overscan: 10, // Number of items to render outside visible area
    enabled: shouldVirtualize,
  });

  // Handle cell change
  const handleCellChange = (rowId: string, columnId: string, newValue: any) => {
    onCellChange(rowId, columnId, newValue);
  };

  // Handle selection change
  const handleSelectionChange = (rowId: string, selected: boolean) => {
    if (onSelectionChange) {
      onSelectionChange(rowId, selected);
    }
  };

  // Empty state
  if (data.length === 0) {
    return (
      <div
        className={styles.emptyState}
        style={{
          color: t.textMuted,
          backgroundColor: t.bgCard,
        }}
      >
        <div className={styles.emptyStateText}>No data to display</div>
      </div>
    );
  }

  // Render with virtual scrolling
  if (shouldVirtualize) {
    const items = rowVirtualizer.getVirtualItems();

    return (
      <div
        ref={parentRef}
        className={styles.container}
        style={{
          maxHeight: `${maxHeight}px`,
          backgroundColor: t.bgCard,
        }}
        role="rowgroup"
      >
        <div
          className={styles.body}
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
          }}
        >
          {items.map((virtualRow) => {
            const rowData = data[virtualRow.index];
            return (
              <div
                key={rowData.id}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <TableRow
                  rowData={rowData}
                  columns={columns}
                  selectable={selectable}
                  isSelected={selectedRowIds.has(rowData.id)}
                  onSelectionChange={(selected) =>
                    handleSelectionChange(rowData.id, selected)
                  }
                  onCellChange={(columnId, newValue) =>
                    handleCellChange(rowData.id, columnId, newValue)
                  }
                  onRowClick={onRowClick}
                  rowActions={rowActions}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Render without virtual scrolling
  return (
    <div
      className={styles.container}
      style={{
        maxHeight: `${maxHeight}px`,
        backgroundColor: t.bgCard,
      }}
      role="rowgroup"
    >
      {data.map((rowData) => (
        <TableRow
          key={rowData.id}
          rowData={rowData}
          columns={columns}
          selectable={selectable}
          isSelected={selectedRowIds.has(rowData.id)}
          onSelectionChange={(selected) =>
            handleSelectionChange(rowData.id, selected)
          }
          onCellChange={(columnId, newValue) =>
            handleCellChange(rowData.id, columnId, newValue)
          }
          onRowClick={onRowClick}
          rowActions={rowActions}
        />
      ))}
    </div>
  );
};
