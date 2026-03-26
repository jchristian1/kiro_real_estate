import React, { useState, useEffect } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, FilterValue, DropdownColumnConfig, NumberFilter, DateFilter } from '../../types';
import styles from './index.module.css';

export interface FilterPopoverProps {
  column: ColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
  onClose: () => void;
  anchorEl: HTMLElement | null;
}

/**
 * FilterPopover component
 * 
 * Renders filter controls based on column type:
 * - Text search for text/longtext columns
 * - Multi-select for dropdown columns
 * - Range inputs for number/date columns
 * - Boolean toggle for checkbox columns
 * 
 * Requirements: 13.2, 13.5, 13.6, 13.7, 13.8
 */
export const FilterPopover: React.FC<FilterPopoverProps> = ({
  column,
  currentFilter,
  onFilterChange,
  onClose,
  anchorEl,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);

  // Position state
  const [position, setPosition] = useState({ top: 0, left: 0 });

  // Calculate popover position
  useEffect(() => {
    if (anchorEl) {
      const rect = anchorEl.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 4,
        left: rect.left,
      });
    }
  }, [anchorEl]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(`.${styles.popover}`)) {
        onClose();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // Render filter controls based on column type
  const renderFilterControls = () => {
    switch (column.type) {
      case 'text':
      case 'longtext':
        return <TextFilter column={column} currentFilter={currentFilter} onFilterChange={onFilterChange} />;
      
      case 'dropdown':
        return <DropdownFilter column={column as DropdownColumnConfig} currentFilter={currentFilter} onFilterChange={onFilterChange} />;
      
      case 'number':
        return <NumberFilterComponent column={column} currentFilter={currentFilter} onFilterChange={onFilterChange} />;
      
      case 'date':
        return <DateFilterComponent column={column} currentFilter={currentFilter} onFilterChange={onFilterChange} />;
      
      case 'checkbox':
        return <BooleanFilter column={column} currentFilter={currentFilter} onFilterChange={onFilterChange} />;
      
      default:
        return <div>Filtering not supported for this column type</div>;
    }
  };

  return (
    <div
      className={styles.popover}
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        backgroundColor: t.bgCard,
        border: `1px solid ${t.border}`,
        borderRadius: '4px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        padding: '12px',
        minWidth: '200px',
        zIndex: 1000,
        color: t.text,
      }}
      role="dialog"
      aria-label={`Filter ${column.label}`}
    >
      <div className={styles.header}>
        <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>
          Filter: {column.label}
        </h4>
      </div>

      <div className={styles.content} style={{ marginTop: '12px' }}>
        {renderFilterControls()}
      </div>

      <div className={styles.actions} style={{ marginTop: '12px', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        <button
          onClick={() => {
            onFilterChange(null);
            onClose();
          }}
          style={{
            padding: '4px 12px',
            fontSize: '12px',
            border: `1px solid ${t.border}`,
            borderRadius: '4px',
            backgroundColor: t.bgCard,
            color: t.text,
            cursor: 'pointer',
          }}
        >
          Clear
        </button>
        <button
          onClick={onClose}
          style={{
            padding: '4px 12px',
            fontSize: '12px',
            border: 'none',
            borderRadius: '4px',
            backgroundColor: t.accent,
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          Apply
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// Text Filter Component
// ============================================================================

interface TextFilterProps {
  column: ColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
}

const TextFilter: React.FC<TextFilterProps> = ({ currentFilter, onFilterChange }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  
  const [value, setValue] = useState(
    currentFilter?.type === 'text' ? currentFilter.value : ''
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setValue(newValue);
    
    if (newValue.trim() === '') {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'text', value: newValue });
    }
  };

  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        Search text
      </label>
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder="Enter search text..."
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: '13px',
          border: `1px solid ${t.border}`,
          borderRadius: '4px',
          backgroundColor: t.bgInput,
          color: t.text,
        }}
        autoFocus
      />
    </div>
  );
};

// ============================================================================
// Dropdown Filter Component
// ============================================================================

interface DropdownFilterProps {
  column: DropdownColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
}

const DropdownFilter: React.FC<DropdownFilterProps> = ({ column, currentFilter, onFilterChange }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  
  const [selectedValues, setSelectedValues] = useState<string[]>(
    currentFilter?.type === 'multi-select' ? currentFilter.values : []
  );

  // Normalize options to { value, label } format
  const normalizedOptions = column.options.map(opt => 
    typeof opt === 'string' ? { value: opt, label: opt } : opt
  );

  const handleToggle = (value: string) => {
    const newSelected = selectedValues.includes(value)
      ? selectedValues.filter(v => v !== value)
      : [...selectedValues, value];
    
    setSelectedValues(newSelected);
    
    if (newSelected.length === 0) {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'multi-select', values: newSelected });
    }
  };

  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        Select values
      </label>
      <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
        {normalizedOptions.map(option => (
          <label
            key={option.value}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '4px 0',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            <input
              type="checkbox"
              checked={selectedValues.includes(option.value)}
              onChange={() => handleToggle(option.value)}
              style={{ marginRight: '8px' }}
            />
            {option.label}
          </label>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// Number Filter Component
// ============================================================================

interface NumberFilterProps {
  column: ColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
}

const NumberFilterComponent: React.FC<NumberFilterProps> = ({ currentFilter, onFilterChange }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  
  // Type narrow to NumberFilter
  const rangeFilter = currentFilter?.type === 'range' ? (currentFilter as NumberFilter) : null;
  
  const [min, setMin] = useState<string>(
    rangeFilter && rangeFilter.min !== undefined ? String(rangeFilter.min) : ''
  );
  const [max, setMax] = useState<string>(
    rangeFilter && rangeFilter.max !== undefined ? String(rangeFilter.max) : ''
  );

  const handleMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMin(value);
    updateFilter(value, max);
  };

  const handleMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMax(value);
    updateFilter(min, value);
  };

  const updateFilter = (minVal: string, maxVal: string) => {
    const minNum = minVal === '' ? undefined : Number(minVal);
    const maxNum = maxVal === '' ? undefined : Number(maxVal);
    
    if (minNum === undefined && maxNum === undefined) {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'range', min: minNum, max: maxNum });
    }
  };

  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        Min value
      </label>
      <input
        type="number"
        value={min}
        onChange={handleMinChange}
        placeholder="No minimum"
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: '13px',
          border: `1px solid ${t.border}`,
          borderRadius: '4px',
          backgroundColor: t.bgInput,
          color: t.text,
          marginBottom: '8px',
        }}
      />
      
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        Max value
      </label>
      <input
        type="number"
        value={max}
        onChange={handleMaxChange}
        placeholder="No maximum"
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: '13px',
          border: `1px solid ${t.border}`,
          borderRadius: '4px',
          backgroundColor: t.bgInput,
          color: t.text,
        }}
      />
    </div>
  );
};

// ============================================================================
// Date Filter Component
// ============================================================================

interface DateFilterProps {
  column: ColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
}

const DateFilterComponent: React.FC<DateFilterProps> = ({ currentFilter, onFilterChange }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  
  // Type narrow to DateFilter
  const rangeFilter = currentFilter?.type === 'range' ? (currentFilter as DateFilter) : null;
  
  const [start, setStart] = useState<string>(
    rangeFilter && rangeFilter.start 
      ? rangeFilter.start.toISOString().split('T')[0] 
      : ''
  );
  const [end, setEnd] = useState<string>(
    rangeFilter && rangeFilter.end 
      ? rangeFilter.end.toISOString().split('T')[0] 
      : ''
  );

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setStart(value);
    updateFilter(value, end);
  };

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEnd(value);
    updateFilter(start, value);
  };

  const updateFilter = (startVal: string, endVal: string) => {
    const startDate = startVal === '' ? undefined : new Date(startVal);
    const endDate = endVal === '' ? undefined : new Date(endVal);
    
    if (startDate === undefined && endDate === undefined) {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'range', start: startDate, end: endDate });
    }
  };

  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        Start date
      </label>
      <input
        type="date"
        value={start}
        onChange={handleStartChange}
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: '13px',
          border: `1px solid ${t.border}`,
          borderRadius: '4px',
          backgroundColor: t.bgInput,
          color: t.text,
          marginBottom: '8px',
        }}
      />
      
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', color: t.textMuted }}>
        End date
      </label>
      <input
        type="date"
        value={end}
        onChange={handleEndChange}
        style={{
          width: '100%',
          padding: '6px 8px',
          fontSize: '13px',
          border: `1px solid ${t.border}`,
          borderRadius: '4px',
          backgroundColor: t.bgInput,
          color: t.text,
        }}
      />
    </div>
  );
};

// ============================================================================
// Boolean Filter Component
// ============================================================================

interface BooleanFilterProps {
  column: ColumnConfig;
  currentFilter?: FilterValue;
  onFilterChange: (filter: FilterValue | null) => void;
}

const BooleanFilter: React.FC<BooleanFilterProps> = ({ currentFilter, onFilterChange }) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  
  const [value, setValue] = useState<'checked' | 'unchecked' | 'any'>(
    currentFilter?.type === 'boolean' ? currentFilter.value : 'any'
  );

  const handleChange = (newValue: 'checked' | 'unchecked' | 'any') => {
    setValue(newValue);
    
    if (newValue === 'any') {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'boolean', value: newValue });
    }
  };

  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', marginBottom: '8px', color: t.textMuted }}>
        Show rows where checkbox is:
      </label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {(['any', 'checked', 'unchecked'] as const).map(option => (
          <label
            key={option}
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            <input
              type="radio"
              name="booleanFilter"
              checked={value === option}
              onChange={() => handleChange(option)}
              style={{ marginRight: '8px' }}
            />
            {option === 'any' ? 'Any' : option === 'checked' ? 'Checked' : 'Unchecked'}
          </label>
        ))}
      </div>
    </div>
  );
};
