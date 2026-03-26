import React from 'react';

// ============================================================================
// Column Types
// ============================================================================

export type ColumnType = 
  | 'text' 
  | 'number' 
  | 'dropdown' 
  | 'checkbox' 
  | 'button' 
  | 'date' 
  | 'longtext' 
  | 'color';

// ============================================================================
// Base Column Configuration
// ============================================================================

export interface BaseColumnConfig<T = any> {
  id: string;
  label: string;
  type: ColumnType;
  width?: number | string;
  minWidth?: number;
  sortable?: boolean;
  filterable?: boolean;
  editable?: boolean;
  required?: boolean;
  defaultValue?: T;
  validation?: (value: T, rowData: RowData) => boolean | string;
  validationMessage?: string;
  cellStyle?: (value: T, rowData: RowData) => React.CSSProperties;
  sortComparator?: (a: T, b: T) => number;
  icon?: string;
  fixed?: boolean;
  hideable?: boolean;
}

// ============================================================================
// Specific Column Configurations
// ============================================================================

export interface TextColumnConfig extends BaseColumnConfig<string> {
  type: 'text';
  maxLength?: number;
  placeholder?: string;
}

export interface NumberColumnConfig extends BaseColumnConfig<number> {
  type: 'number';
  min?: number;
  max?: number;
  step?: number;
  format?: 'currency' | 'percentage' | 'decimal';
  decimalPlaces?: number;
}

export interface DropdownColumnConfig extends BaseColumnConfig<string> {
  type: 'dropdown';
  options: Array<string | { value: string; label: string }>;
  allowCustom?: boolean;
  optionsLoader?: () => Promise<Array<string | { value: string; label: string }>>;
}

export interface CheckboxColumnConfig extends BaseColumnConfig<boolean> {
  type: 'checkbox';
  disabled?: (rowData: RowData) => boolean;
}

export interface ButtonColumnConfig extends BaseColumnConfig<void> {
  type: 'button';
  buttonLabel: string;
  buttonVariant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  buttonIcon?: string;
  buttonDisabled?: (rowData: RowData) => boolean;
  onClick: (rowData: RowData) => void;
}

export interface DateColumnConfig extends BaseColumnConfig<string> {
  type: 'date';
  dateFormat?: string;
  minDate?: Date;
  maxDate?: Date;
}

export interface LongTextColumnConfig extends BaseColumnConfig<string> {
  type: 'longtext';
  maxLength?: number;
  maxHeight?: number;
  placeholder?: string;
}

export interface ColorColumnConfig extends BaseColumnConfig<string> {
  type: 'color';
  colorOptions?: Array<{ value: string; label: string }>;
}

export type ColumnConfig = 
  | TextColumnConfig 
  | NumberColumnConfig 
  | DropdownColumnConfig 
  | CheckboxColumnConfig 
  | ButtonColumnConfig 
  | DateColumnConfig 
  | LongTextColumnConfig 
  | ColorColumnConfig;

// ============================================================================
// Row Data
// ============================================================================

export interface RowData {
  id: string;
  [columnId: string]: any;
}

// ============================================================================
// Row Actions
// ============================================================================

export interface RowAction {
  id: string;
  label: string;
  icon?: string;
  onClick: (rowData: RowData) => void | Promise<void>;
  disabled?: (rowData: RowData) => boolean;
  confirm?: {
    title: string;
    message: string;
  };
  separator?: boolean;
}

// ============================================================================
// Filter Types
// ============================================================================

export type TextFilter = { 
  type: 'text'; 
  value: string;
};

export type NumberFilter = { 
  type: 'range'; 
  min?: number; 
  max?: number;
};

export type DateFilter = { 
  type: 'range'; 
  start?: Date; 
  end?: Date;
};

export type DropdownFilter = { 
  type: 'multi-select'; 
  values: string[];
};

export type CheckboxFilter = { 
  type: 'boolean'; 
  value: 'checked' | 'unchecked' | 'any';
};

export type FilterValue = 
  | TextFilter 
  | NumberFilter 
  | DateFilter 
  | DropdownFilter 
  | CheckboxFilter;

// ============================================================================
// State Types
// ============================================================================

export interface EditingCell {
  rowId: string;
  columnId: string;
  originalValue: any;
}

export interface SortState {
  columnId: string;
  direction: 'asc' | 'desc';
}

export type FilterState = Map<string, FilterValue>;

export type ColumnOrder = string[];

export type ColumnVisibility = Set<string>;

export type SelectionState = Set<string>;

export interface ValidationError {
  rowId: string;
  columnId: string;
  message: string;
}

// ============================================================================
// Storage Types
// ============================================================================

export interface StoredTableState {
  columnOrder: string[];
  columnVisibility: string[];
  sortState: SortState | null;
  pageSize: number;
}

// ============================================================================
// Validation Result
// ============================================================================

export interface ValidationResult {
  valid: boolean;
  message?: string;
}

// ============================================================================
// Main Component Props
// ============================================================================

export interface DynamicTableProps {
  // Data
  columns: ColumnConfig[];
  data: RowData[];
  
  // Callbacks
  onCellChange?: (
    rowId: string, 
    columnId: string, 
    oldValue: any, 
    newValue: any
  ) => void | Promise<void>;
  onRowAdd?: (rowData: RowData) => boolean | Promise<boolean>;
  onRowDelete?: (rowId: string) => boolean | Promise<boolean>;
  onBulkChange?: (
    changes: Array<{ 
      rowId: string; 
      columnId: string; 
      oldValue: any; 
      newValue: any;
    }>
  ) => void | Promise<void>;
  onSelectionChange?: (selectedRowIds: string[]) => void;
  onColumnOrderChange?: (columnOrder: string[]) => void;
  onColumnVisibilityChange?: (visibleColumns: string[]) => void;
  
  // Features
  selectable?: boolean;
  selectionMode?: 'single' | 'multiple';
  selectedRowIds?: string[];
  allowAdd?: boolean;
  addRowPosition?: 'top' | 'bottom';
  allowDelete?: boolean;
  deleteConfirmMessage?: string;
  rowActions?: RowAction[];
  allowExport?: boolean;
  allowColumnReorder?: boolean;
  allowColumnToggle?: boolean;
  
  // Performance
  pagination?: boolean;
  pageSize?: number;
  virtualScrolling?: boolean;
  onLoadMore?: () => void | Promise<void>;
  
  // UI
  responsive?: boolean;
  mobileColumns?: string[];
  storageKey?: string;
  errorBoundary?: boolean;
  
  // Styling
  className?: string;
  style?: React.CSSProperties;
}
