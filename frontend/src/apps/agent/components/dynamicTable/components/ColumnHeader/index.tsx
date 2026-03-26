import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, SortState } from '../../types';
import styles from './index.module.css';

export interface ColumnHeaderProps {
  column: ColumnConfig;
  sortState?: SortState | null;
  onSortChange?: (columnId: string) => void;
  onFilterClick?: (columnId: string) => void;
  hasActiveFilter?: boolean;
  allowReorder?: boolean;
  onDragStart?: (columnId: string) => void;
}

/**
 * ColumnHeader component
 * 
 * Renders a column header with:
 * - Column label and optional icon
 * - Sort indicator and click handler (if sortable)
 * - Filter button (if filterable)
 * - Drag handle for reordering (if allowReorder)
 * - Theme-integrated styling
 * 
 * Requirements: 12.1, 12.2, 13.1, 13.2, 24.1
 */
export const ColumnHeader: React.FC<ColumnHeaderProps> = ({
  column,
  sortState,
  onSortChange,
  onFilterClick,
  hasActiveFilter = false,
  allowReorder = false,
  onDragStart,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  // Determine if this column is currently sorted
  const isSorted = sortState?.columnId === column.id;
  const sortDirection = isSorted ? sortState?.direction : null;

  // Handle sort click
  const handleSortClick = () => {
    if (column.sortable && onSortChange) {
      onSortChange(column.id);
    }
  };

  // Handle filter button click
  const handleFilterClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (column.filterable && onFilterClick) {
      onFilterClick(column.id);
    }
  };

  // Handle drag start
  const handleDragStart = (e: React.DragEvent) => {
    e.stopPropagation();
    if (allowReorder && !column.fixed && onDragStart) {
      onDragStart(column.id);
    }
  };

  // Get sort indicator icon
  const getSortIcon = () => {
    if (!isSorted) return null;
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  return (
    <div
      className={styles.header}
      style={{
        '--header-hover-bg': t.bgCardHover,
        backgroundColor: t.bgCard,
        borderBottom: `2px solid ${t.border}`,
        borderRight: `1px solid ${t.border}`,
        color: t.text,
        width: column.width || 'auto',
        minWidth: column.minWidth || 100,
      } as React.CSSProperties}
      onClick={column.sortable ? handleSortClick : undefined}
      role="columnheader"
      aria-sort={
        isSorted
          ? sortDirection === 'asc'
            ? 'ascending'
            : 'descending'
          : 'none'
      }
      aria-label={column.label}
    >
      {/* Drag handle */}
      {allowReorder && !column.fixed && (
        <div
          className={styles.dragHandle}
          draggable
          onDragStart={handleDragStart}
          style={{ color: t.textMuted }}
          aria-label="Drag to reorder"
        >
          ⋮⋮
        </div>
      )}

      {/* Header content */}
      <div className={styles.headerContent}>
        {/* Icon */}
        {column.icon && (
          <span className={styles.icon} aria-hidden="true">
            {column.icon}
          </span>
        )}

        {/* Label */}
        <span className={styles.label}>{column.label}</span>

        {/* Sort indicator */}
        {column.sortable && (
          <span
            className={styles.sortIndicator}
            style={{ color: isSorted ? t.accent : t.textMuted }}
            aria-hidden="true"
          >
            {getSortIcon() || '⇅'}
          </span>
        )}
      </div>

      {/* Filter button */}
      {column.filterable && (
        <button
          className={`${styles.filterButton} ${hasActiveFilter ? styles.active : ''}`}
          onClick={handleFilterClick}
          style={{
            color: hasActiveFilter ? t.accent : t.textMuted,
          }}
          aria-label={`Filter ${column.label}`}
          aria-pressed={hasActiveFilter}
        >
          🔍
        </button>
      )}
    </div>
  );
};
