# Dynamic Editable Table Component

Excel-like editable table component for React with inline editing, sorting, filtering, and full accessibility support.

## Directory Structure

```
dynamicTable/
├── index.tsx                 # Barrel exports
├── types.ts                  # TypeScript interfaces and types
├── DynamicTable.tsx          # Main component
├── hooks/                    # Custom hooks
│   ├── useDataState.ts
│   ├── useSortState.ts
│   ├── useFilterState.ts
│   ├── useSelectionState.ts
│   ├── useLocalStorage.ts
│   ├── useTheme.ts
│   └── useResponsive.ts
├── components/               # Sub-components
│   ├── TableToolbar.tsx
│   ├── TableHeader.tsx
│   ├── ColumnHeader.tsx
│   ├── VirtualTableBody.tsx
│   ├── TableRow.tsx
│   ├── TableCell.tsx
│   ├── TableFooter.tsx
│   ├── AddRowButton.tsx
│   ├── ExportButton.tsx
│   ├── ColumnVisibilityToggle.tsx
│   ├── SelectionSummary.tsx
│   ├── SelectionCell.tsx
│   ├── SelectionHeaderCell.tsx
│   ├── ActionsCell.tsx
│   ├── FilterPopover.tsx
│   └── ErrorBoundary.tsx
├── renderers/                # Cell renderers
│   ├── CellRenderer.tsx
│   ├── TextCellRenderer.tsx
│   ├── NumberCellRenderer.tsx
│   ├── DropdownCellRenderer.tsx
│   ├── CheckboxCellRenderer.tsx
│   ├── ButtonCellRenderer.tsx
│   ├── DateCellRenderer.tsx
│   ├── LongTextCellRenderer.tsx
│   └── ColorCellRenderer.tsx
├── editors/                  # Cell editors
│   ├── CellEditor.tsx
│   ├── TextCellEditor.tsx
│   ├── NumberCellEditor.tsx
│   ├── DropdownCellEditor.tsx
│   ├── CheckboxCellEditor.tsx
│   ├── DateCellEditor.tsx
│   ├── LongTextCellEditor.tsx
│   └── ColorCellEditor.tsx
├── utils/                    # Utility functions
│   ├── validation.ts
│   ├── sorting.ts
│   ├── filtering.ts
│   ├── export.ts
│   └── colorUtils.ts
└── __tests__/                # Tests
    ├── properties/           # Property-based tests
    └── unit/                 # Unit tests
```

## Usage Example

```tsx
import { DynamicTable, ColumnConfig, RowData } from '@/components/dynamicTable';

const columns: ColumnConfig[] = [
  { id: 'name', label: 'Name', type: 'text', editable: true, sortable: true },
  { id: 'email', label: 'Email', type: 'text', editable: true },
  { id: 'status', label: 'Status', type: 'dropdown', options: ['Active', 'Inactive'], editable: true },
  { id: 'verified', label: 'Verified', type: 'checkbox', editable: true },
];

const data: RowData[] = [
  { id: '1', name: 'John Doe', email: 'john@example.com', status: 'Active', verified: true },
  { id: '2', name: 'Jane Smith', email: 'jane@example.com', status: 'Inactive', verified: false },
];

function MyComponent() {
  const handleCellChange = async (rowId, columnId, oldValue, newValue) => {
    console.log('Cell changed:', { rowId, columnId, oldValue, newValue });
    // Sync with backend
  };

  return (
    <DynamicTable
      columns={columns}
      data={data}
      onCellChange={handleCellChange}
      selectable
      allowAdd
      allowDelete
      allowExport
    />
  );
}
```

## Features

- ✅ 8 column types: text, number, dropdown, checkbox, button, date, longtext, color
- ✅ Inline editing with keyboard navigation (Tab, Enter, Escape)
- ✅ Sorting and filtering
- ✅ Row selection (single/multiple)
- ✅ Add/delete rows
- ✅ Export to CSV/Excel
- ✅ Column reordering and visibility toggle
- ✅ Virtual scrolling for large datasets
- ✅ Theme integration
- ✅ Full accessibility (WCAG 2.1 AA)
- ✅ Responsive design (mobile card layout)

## Dependencies

- `@tanstack/react-virtual` - Virtual scrolling
- `@dnd-kit/core` & `@dnd-kit/sortable` - Drag and drop
- `zod` - Runtime validation
- `date-fns` - Date formatting
- `react-colorful` - Color picker
- `xlsx` - Excel export
- `fast-check` - Property-based testing
