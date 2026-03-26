import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { FilterState, FilterValue, RowData, ColumnConfig } from '../types';

/**
 * useFilterState hook
 * 
 * Manages filter state and application logic:
 * - Stores active filters in a Map<columnId, filterValue>
 * - Applies filters to data
 * - Debounces filter inputs by 300ms
 * 
 * Requirements: 13.3, 13.4, 20.2
 */
export const useFilterState = (
  data: RowData[],
  columns: ColumnConfig[]
) => {
  const [filterState, setFilterState] = useState<FilterState>(new Map());
  const [pendingFilterState, setPendingFilterState] = useState<FilterState>(new Map());
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Apply pending filters after debounce delay
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      setFilterState(new Map(pendingFilterState));
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [pendingFilterState]);

  /**
   * Set filter for a specific column (debounced)
   */
  const setFilter = useCallback((columnId: string, filterValue: FilterValue | null) => {
    setPendingFilterState((current) => {
      const newState = new Map(current);
      if (filterValue === null) {
        newState.delete(columnId);
      } else {
        newState.set(columnId, filterValue);
      }
      return newState;
    });
  }, []);

  /**
   * Clear filter for a specific column (immediate, no debounce)
   */
  const clearFilter = useCallback((columnId: string) => {
    setPendingFilterState((current) => {
      const newState = new Map(current);
      newState.delete(columnId);
      return newState;
    });
    // Also clear immediately from active state
    setFilterState((current) => {
      const newState = new Map(current);
      newState.delete(columnId);
      return newState;
    });
  }, []);

  /**
   * Clear all filters (immediate, no debounce)
   */
  const clearAllFilters = useCallback(() => {
    setPendingFilterState(new Map());
    setFilterState(new Map());
  }, []);

  /**
   * Check if a row matches a specific filter
   */
  const matchesFilter = useCallback(
    (row: RowData, columnId: string, filter: FilterValue): boolean => {
      const value = row[columnId];
      const column = columns.find((col) => col.id === columnId);

      if (!column) return true;

      switch (filter.type) {
        case 'text': {
          // Case-insensitive text search
          const searchValue = filter.value.toLowerCase();
          const cellValue = String(value || '').toLowerCase();
          return cellValue.includes(searchValue);
        }

        case 'range': {
          if (column.type === 'number') {
            const numValue = Number(value);
            if (isNaN(numValue)) return false;
            
            const { min, max } = filter as { min?: number; max?: number };
            if (min !== undefined && numValue < min) return false;
            if (max !== undefined && numValue > max) return false;
            return true;
          }

          if (column.type === 'date') {
            const dateValue = value ? new Date(value) : null;
            if (!dateValue || isNaN(dateValue.getTime())) return false;

            const { start, end } = filter as { start?: Date; end?: Date };
            if (start && dateValue < start) return false;
            if (end && dateValue > end) return false;
            return true;
          }

          return true;
        }

        case 'multi-select': {
          const selectedValues = filter.values;
          if (selectedValues.length === 0) return true;
          return selectedValues.includes(String(value));
        }

        case 'boolean': {
          const boolValue = Boolean(value);
          if (filter.value === 'any') return true;
          if (filter.value === 'checked') return boolValue === true;
          if (filter.value === 'unchecked') return boolValue === false;
          return true;
        }

        default:
          return true;
      }
    },
    [columns]
  );

  /**
   * Apply all active filters to the data
   */
  const filteredData = useMemo(() => {
    if (filterState.size === 0) {
      return data;
    }

    return data.filter((row) => {
      // Row must match ALL active filters
      for (const [columnId, filter] of filterState.entries()) {
        if (!matchesFilter(row, columnId, filter)) {
          return false;
        }
      }
      return true;
    });
  }, [data, filterState, matchesFilter]);

  /**
   * Check if a column has an active filter
   */
  const hasFilter = useCallback(
    (columnId: string): boolean => {
      return filterState.has(columnId);
    },
    [filterState]
  );

  /**
   * Get filter value for a column
   */
  const getFilter = useCallback(
    (columnId: string): FilterValue | undefined => {
      return filterState.get(columnId);
    },
    [filterState]
  );

  return {
    filterState,
    filteredData,
    setFilter,
    clearFilter,
    clearAllFilters,
    hasFilter,
    getFilter,
  };
};
