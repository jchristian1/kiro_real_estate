import { ColumnConfig, RowData } from '../types';

/**
 * Sort comparator utilities
 * 
 * Provides default comparators for each column type and handles null/undefined values.
 * Supports custom sortComparator from column config.
 * 
 * Requirements: 12.5
 */

/**
 * Compare two values with null/undefined handling
 * Null/undefined values are always sorted to the end
 */
const compareWithNulls = (
  a: any,
  b: any,
  compareFn: (a: any, b: any) => number
): number => {
  // Handle null/undefined
  if (a == null && b == null) return 0;
  if (a == null) return 1; // null goes to end
  if (b == null) return -1; // null goes to end

  return compareFn(a, b);
};

/**
 * Text comparator (case-insensitive)
 */
const textComparator = (a: string, b: string): number => {
  const aStr = String(a).toLowerCase();
  const bStr = String(b).toLowerCase();
  return aStr.localeCompare(bStr);
};

/**
 * Number comparator
 */
const numberComparator = (a: number, b: number): number => {
  return a - b;
};

/**
 * Date comparator (handles ISO 8601 strings and Date objects)
 */
const dateComparator = (a: string | Date, b: string | Date): number => {
  const dateA = typeof a === 'string' ? new Date(a) : a;
  const dateB = typeof b === 'string' ? new Date(b) : b;
  return dateA.getTime() - dateB.getTime();
};

/**
 * Boolean comparator (false < true)
 */
const booleanComparator = (a: boolean, b: boolean): number => {
  return a === b ? 0 : a ? 1 : -1;
};

/**
 * Get the appropriate comparator for a column type
 */
const getDefaultComparator = (columnType: string): (a: any, b: any) => number => {
  switch (columnType) {
    case 'text':
    case 'longtext':
    case 'dropdown':
    case 'color':
      return textComparator;
    
    case 'number':
      return numberComparator;
    
    case 'date':
      return dateComparator;
    
    case 'checkbox':
      return booleanComparator;
    
    default:
      return textComparator;
  }
};

/**
 * Sort data by column
 */
export const sortData = (
  data: RowData[],
  column: ColumnConfig,
  direction: 'asc' | 'desc'
): RowData[] => {
  // Use custom comparator if provided, otherwise use default
  const compareFn = column.sortComparator || getDefaultComparator(column.type);

  // Create a copy to avoid mutating original array
  const sortedData = [...data];

  sortedData.sort((rowA, rowB) => {
    const valueA = rowA[column.id];
    const valueB = rowB[column.id];

    // Compare with null handling
    const result = compareWithNulls(valueA, valueB, compareFn);

    // Apply direction
    return direction === 'asc' ? result : -result;
  });

  return sortedData;
};

/**
 * Apply sorting to data if sort state exists
 */
export const applySorting = (
  data: RowData[],
  columns: ColumnConfig[],
  sortState: { columnId: string; direction: 'asc' | 'desc' } | null
): RowData[] => {
  if (!sortState) {
    return data;
  }

  const column = columns.find((col) => col.id === sortState.columnId);
  if (!column || !column.sortable) {
    return data;
  }

  return sortData(data, column, sortState.direction);
};
