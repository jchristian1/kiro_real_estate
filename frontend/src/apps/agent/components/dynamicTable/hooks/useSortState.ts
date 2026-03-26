import { useState, useCallback } from 'react';
import { SortState } from '../types';

/**
 * useSortState hook
 * 
 * Manages sorting state with toggle logic:
 * - Click 1: Sort ascending
 * - Click 2: Sort descending
 * - Click 3: Clear sort (back to unsorted)
 * 
 * Persists sort state across re-renders.
 * 
 * Requirements: 12.1, 12.2, 12.3, 12.6
 */
export const useSortState = (initialSort?: SortState | null) => {
  const [sortState, setSortState] = useState<SortState | null>(initialSort || null);

  /**
   * Toggle sort for a column
   * Cycles through: none → asc → desc → none
   */
  const toggleSort = useCallback((columnId: string) => {
    setSortState((current) => {
      // If sorting a different column, start with ascending
      if (!current || current.columnId !== columnId) {
        return { columnId, direction: 'asc' };
      }

      // If currently ascending, switch to descending
      if (current.direction === 'asc') {
        return { columnId, direction: 'desc' };
      }

      // If currently descending, clear sort
      return null;
    });
  }, []);

  /**
   * Set sort state directly
   */
  const setSort = useCallback((newSort: SortState | null) => {
    setSortState(newSort);
  }, []);

  /**
   * Clear sort state
   */
  const clearSort = useCallback(() => {
    setSortState(null);
  }, []);

  return {
    sortState,
    toggleSort,
    setSort,
    clearSort,
  };
};
