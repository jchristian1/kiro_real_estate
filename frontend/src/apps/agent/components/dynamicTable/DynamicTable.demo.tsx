import React from 'react';
import { DynamicTable } from './DynamicTable';
import { ColumnConfig, RowData } from './types';

/**
 * Demo component showing filtering functionality integration (Task 7.4)
 * 
 * This demo demonstrates:
 * - Filter buttons on filterable columns
 * - Filter popover opening/closing
 * - Text search filter (Name column)
 * - Multi-select filter (Status column)
 * - Range filter (Age column)
 * - Active filter indicators
 * - Filter + Sort combination
 * - Multiple active filters
 */
export const DynamicTableFilteringDemo: React.FC = () => {
  const columns: ColumnConfig[] = [
    {
      id: 'name',
      label: 'Name',
      type: 'text',
      sortable: true,
      filterable: true,
      width: 200,
    },
    {
      id: 'age',
      label: 'Age',
      type: 'number',
      sortable: true,
      filterable: true,
      width: 100,
    },
    {
      id: 'status',
      label: 'Status',
      type: 'dropdown',
      options: ['Active', 'Inactive', 'Pending'],
      sortable: true,
      filterable: true,
      width: 150,
    },
    {
      id: 'department',
      label: 'Department',
      type: 'text',
      sortable: true,
      filterable: true,
      width: 150,
    },
    {
      id: 'joinDate',
      label: 'Join Date',
      type: 'date',
      sortable: true,
      filterable: true,
      width: 150,
    },
  ];

  const data: RowData[] = [
    { 
      id: '1', 
      name: 'Alice Johnson', 
      age: 30, 
      status: 'Active', 
      department: 'Engineering',
      joinDate: '2020-01-15'
    },
    { 
      id: '2', 
      name: 'Bob Smith', 
      age: 25, 
      status: 'Inactive', 
      department: 'Sales',
      joinDate: '2021-03-20'
    },
    { 
      id: '3', 
      name: 'Charlie Brown', 
      age: 35, 
      status: 'Active', 
      department: 'Engineering',
      joinDate: '2019-06-10'
    },
    { 
      id: '4', 
      name: 'David Lee', 
      age: 28, 
      status: 'Active', 
      department: 'Marketing',
      joinDate: '2020-11-05'
    },
    { 
      id: '5', 
      name: 'Eve Wilson', 
      age: 32, 
      status: 'Pending', 
      department: 'Engineering',
      joinDate: '2022-02-14'
    },
    { 
      id: '6', 
      name: 'Frank Miller', 
      age: 29, 
      status: 'Active', 
      department: 'Sales',
      joinDate: '2021-08-22'
    },
    { 
      id: '7', 
      name: 'Grace Davis', 
      age: 27, 
      status: 'Inactive', 
      department: 'Marketing',
      joinDate: '2022-05-30'
    },
    { 
      id: '8', 
      name: 'Henry Garcia', 
      age: 31, 
      status: 'Active', 
      department: 'Engineering',
      joinDate: '2020-09-18'
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <h1>Dynamic Table - Filtering Integration Demo</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <h2>Features Demonstrated:</h2>
        <ul>
          <li>✅ Filter buttons displayed on filterable columns</li>
          <li>✅ Click filter button to open FilterPopover</li>
          <li>✅ Text search filter (Name, Department columns)</li>
          <li>✅ Multi-select filter (Status column)</li>
          <li>✅ Range filter (Age, Join Date columns)</li>
          <li>✅ Active filter indicators (colored filter icon)</li>
          <li>✅ Filters applied before sorting</li>
          <li>✅ Multiple filters can be active simultaneously</li>
          <li>✅ Filter debouncing (300ms)</li>
          <li>✅ Clear individual filters</li>
        </ul>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h2>Try These Actions:</h2>
        <ol>
          <li>Click the 🔍 icon on the "Name" column header</li>
          <li>Type "e" in the search box - watch the filtered count update</li>
          <li>Click "Apply" to close the popover</li>
          <li>Notice the filter icon is now highlighted (active filter indicator)</li>
          <li>Click the 🔍 icon on the "Status" column</li>
          <li>Select "Active" - see multiple filters working together</li>
          <li>Click the "Name" column header to sort - filters remain active</li>
          <li>Click "Clear" in any filter popover to remove that filter</li>
        </ol>
      </div>

      <DynamicTable 
        columns={columns} 
        data={data}
        style={{ maxWidth: '1200px' }}
      />

      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
        <h3>Implementation Notes:</h3>
        <p>
          <strong>Task 7.4 - Integrate filtering into DynamicTable</strong> is complete:
        </p>
        <ul>
          <li>✅ useFilterState hook imported and used in DynamicTable</li>
          <li>✅ Filters applied to data before sorting (filteredData → applySorting)</li>
          <li>✅ Filter indicators displayed on column headers when filters are active</li>
          <li>✅ Filter state changes handled (opening/closing FilterPopover, applying/clearing filters)</li>
          <li>✅ FilterButton in ColumnHeader connected to open FilterPopover</li>
          <li>✅ Filtered data passed through processing pipeline</li>
        </ul>
        <p>
          The table body rendering is intentionally a placeholder as it will be implemented in subsequent tasks.
          The filtering logic is fully functional and ready for integration with the table body.
        </p>
      </div>
    </div>
  );
};

export default DynamicTableFilteringDemo;
