import React, { useState, useMemo } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { DynamicTableProps } from './types';
import { TableHeader } from './components/TableHeader';
import { FilterPopover } from './components/FilterPopover';
import { useFilterState } from './hooks/useFilterState';
import { useSortState } from './hooks/useSortState';
import { applySorting } from './utils/sortComparators';

/**
 * DynamicTable - Excel-like editable table component
 * 
 * Main component that orchestrates all table functionality including:
 * - Inline editing with 8 column types
 * - Sorting and filtering
 * - Row selection and actions
 * - Virtual scrolling for performance
 * - Full accessibility support
 * 
 * This component will be fully implemented in Task 25
 * Currently implements: Sorting (Task 6) and Filtering (Task 7)
 */
export const DynamicTable: React.FC<DynamicTableProps> = (props) => {
  const { 
    columns, 
    data, 
    className, 
    style,
    selectable = false,
    allowColumnReorder = false,
    rowActions,
  } = props;

  const { theme } = useTheme();
  const t = getTokens(theme);

  // Sorting state
  const { sortState, toggleSort } = useSortState();

  // Filtering state
  const {
    filterState,
    filteredData,
    setFilter,
    clearFilter,
    hasFilter,
    getFilter,
  } = useFilterState(data, columns);

  // Filter popover state
  const [filterPopoverState, setFilterPopoverState] = useState<{
    columnId: string;
    anchorEl: HTMLElement;
  } | null>(null);

  // Apply filtering first, then sorting (Requirements 13.3, 13.4)
  const processedData = useMemo(() => {
    return applySorting(filteredData, columns, sortState);
  }, [filteredData, columns, sortState]);

  // Handle filter button click
  const handleFilterClick = (columnId: string) => {
    const filterButton = document.querySelector(
      `[aria-label="Filter ${columns.find(c => c.id === columnId)?.label}"]`
    ) as HTMLElement;
    
    if (filterButton) {
      setFilterPopoverState({ columnId, anchorEl: filterButton });
    }
  };

  // Handle filter change
  const handleFilterChange = (columnId: string, filter: any) => {
    setFilter(columnId, filter);
  };

  // Close filter popover
  const closeFilterPopover = () => {
    setFilterPopoverState(null);
  };

  // Get active filters set
  const activeFilters = new Set(
    Array.from(filterState.keys()).filter(columnId => hasFilter(columnId))
  );

  return (
    <div className={className} style={style}>
      <div style={{ 
        border: `1px solid ${t.border}`, 
        borderRadius: '4px',
        backgroundColor: t.bgCard,
        overflow: 'hidden',
      }}>
        {/* Table Header */}
        <TableHeader
          columns={columns}
          selectable={selectable}
          sortState={sortState}
          onSortChange={toggleSort}
          onFilterClick={handleFilterClick}
          activeFilters={activeFilters}
          allowReorder={allowColumnReorder}
          rowActions={rowActions}
        />

        {/* Table Body - Placeholder for now */}
        <div style={{ padding: '20px', color: t.text }}>
          <p>Filtered Rows: {processedData.length} / {data.length}</p>
          <p>Active Filters: {activeFilters.size}</p>
          <p>Sort: {sortState ? `${sortState.columnId} (${sortState.direction})` : 'None'}</p>
          <p>Table body will be implemented in subsequent tasks.</p>
        </div>

        {/* Filter Popover */}
        {filterPopoverState && (
          <FilterPopover
            column={columns.find(c => c.id === filterPopoverState.columnId)!}
            currentFilter={getFilter(filterPopoverState.columnId)}
            onFilterChange={(filter) => handleFilterChange(filterPopoverState.columnId, filter)}
            onClose={closeFilterPopover}
            anchorEl={filterPopoverState.anchorEl}
          />
        )}
      </div>
    </div>
  );
};
