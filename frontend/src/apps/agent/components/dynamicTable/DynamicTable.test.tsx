import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { DynamicTable } from './DynamicTable';
import { ColumnConfig, RowData } from './types';

// Mock ThemeContext
vi.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
  }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock theme utils
vi.mock('@/shared/utils/theme', () => ({
  getTokens: () => ({
    bgCard: '#ffffff',
    bgCardHover: '#f5f5f5',
    bgInput: '#ffffff',
    border: '#e0e0e0',
    text: '#000000',
    textMuted: '#666666',
    accent: '#0066cc',
  }),
}));

// Wrapper component (no longer needs ThemeProvider since it's mocked)
const TestWrapper = ({ children }: { children: React.ReactNode }) => <>{children}</>;

describe('DynamicTable - Filtering Integration (Task 7.4)', () => {
  const columns: ColumnConfig[] = [
    {
      id: 'name',
      label: 'Name',
      type: 'text',
      sortable: true,
      filterable: true,
    },
    {
      id: 'age',
      label: 'Age',
      type: 'number',
      sortable: true,
      filterable: true,
    },
    {
      id: 'status',
      label: 'Status',
      type: 'dropdown',
      options: ['Active', 'Inactive'],
      filterable: true,
    },
  ];

  const data: RowData[] = [
    { id: '1', name: 'Alice', age: 30, status: 'Active' },
    { id: '2', name: 'Bob', age: 25, status: 'Inactive' },
    { id: '3', name: 'Charlie', age: 35, status: 'Active' },
    { id: '4', name: 'David', age: 28, status: 'Active' },
  ];

  it('should display filter buttons on filterable columns', () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // All three columns are filterable, so we should see 3 filter buttons
    const filterButtons = screen.getAllByLabelText(/Filter/i);
    expect(filterButtons).toHaveLength(3);
  });

  it('should open filter popover when filter button is clicked', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Click the filter button for the Name column
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    // Wait for popover to appear
    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });
  });

  it('should apply text filter and update filtered data count', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Initial state: all 4 rows visible
    expect(screen.getByText(/Filtered Rows: 4 \/ 4/)).toBeInTheDocument();

    // Open filter popover for Name column
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    // Wait for popover and enter filter text
    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Enter search text...');
    fireEvent.change(searchInput, { target: { value: 'ali' } });

    // Wait for debounce (300ms) and check filtered count
    await waitFor(
      () => {
        expect(screen.getByText(/Filtered Rows: 1 \/ 4/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });

  it('should show active filter indicator on column header', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Open filter popover for Name column
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    // Enter filter text
    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Enter search text...');
    fireEvent.change(searchInput, { target: { value: 'ali' } });

    // Wait for filter to be applied
    await waitFor(
      () => {
        expect(screen.getByText(/Active Filters: 1/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );

    // Filter button should have aria-pressed="true"
    expect(nameFilterButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('should clear filter when Clear button is clicked', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Apply a filter first
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Enter search text...');
    fireEvent.change(searchInput, { target: { value: 'ali' } });

    // Wait for filter to be applied
    await waitFor(
      () => {
        expect(screen.getByText(/Filtered Rows: 1 \/ 4/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );

    // Click Clear button
    const clearButton = screen.getByText('Clear');
    fireEvent.click(clearButton);

    // Filter should be cleared
    await waitFor(() => {
      expect(screen.getByText(/Filtered Rows: 4 \/ 4/)).toBeInTheDocument();
      expect(screen.getByText(/Active Filters: 0/)).toBeInTheDocument();
    });
  });

  it('should apply filters before sorting', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Apply a filter first
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Enter search text...');
    fireEvent.change(searchInput, { target: { value: 'a' } }); // Matches Alice, Charlie, David

    // Wait for filter to be applied
    await waitFor(
      () => {
        expect(screen.getByText(/Filtered Rows: 3 \/ 4/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );

    // Close the popover
    const applyButton = screen.getByText('Apply');
    fireEvent.click(applyButton);

    // Now click to sort by Name
    const nameHeader = screen.getByText('Name');
    fireEvent.click(nameHeader);

    // Verify sort is applied (check sort indicator)
    await waitFor(() => {
      expect(screen.getByText(/Sort: name \(asc\)/)).toBeInTheDocument();
    });

    // Filtered count should remain the same (filters applied before sorting)
    expect(screen.getByText(/Filtered Rows: 3 \/ 4/)).toBeInTheDocument();
  });

  it('should support multiple active filters', async () => {
    render(
      <TestWrapper>
        <DynamicTable columns={columns} data={data} />
      </TestWrapper>
    );

    // Apply first filter on Name
    const nameFilterButton = screen.getByLabelText('Filter Name');
    fireEvent.click(nameFilterButton);

    await waitFor(() => {
      expect(screen.getByText('Filter: Name')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Enter search text...');
    fireEvent.change(searchInput, { target: { value: 'a' } });

    // Wait for first filter
    await waitFor(
      () => {
        expect(screen.getByText(/Filtered Rows: 3 \/ 4/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );

    // Close popover
    const applyButton = screen.getByText('Apply');
    fireEvent.click(applyButton);

    // Apply second filter on Status
    const statusFilterButton = screen.getByLabelText('Filter Status');
    fireEvent.click(statusFilterButton);

    await waitFor(() => {
      expect(screen.getByText('Filter: Status')).toBeInTheDocument();
    });

    // Select "Active" in multi-select
    const activeCheckbox = screen.getByLabelText('Active');
    fireEvent.click(activeCheckbox);

    // Wait for second filter (should show Alice, Charlie, David with 'a' AND Active status)
    await waitFor(
      () => {
        expect(screen.getByText(/Filtered Rows: 2 \/ 4/)).toBeInTheDocument(); // Alice and Charlie
        expect(screen.getByText(/Active Filters: 2/)).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });
});
