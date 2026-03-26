import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { ColumnConfig, RowData, ValidationResult } from '../../types';
import styles from './index.module.css';

export interface CellEditorProps {
  value: any;
  column: ColumnConfig;
  rowData: RowData;
  onSave: (newValue: any) => void;
  onCancel: () => void;
  children?: React.ReactNode;
}

/**
 * Base CellEditor component
 * 
 * Provides:
 * - Validation logic with error display
 * - Keyboard event handling (Enter, Escape, Tab)
 * - Loading indicator for async operations
 * - Error display (red border, error message)
 * - Theme-integrated styling
 * 
 * Requirements: 2.2, 2.3, 2.4, 2.5, 10.3, 10.4, 22.1, 22.2
 */
export const CellEditor: React.FC<CellEditorProps> = ({
  value: initialValue,
  column,
  rowData,
  onSave,
  onCancel,
  children,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Validate value
  const validate = (val: any): ValidationResult => {
    // Required field check
    if (column.required && (val === null || val === undefined || val === '')) {
      return { 
        valid: false, 
        message: column.validationMessage || 'This field is required' 
      };
    }

    // Custom validation
    if (column.validation) {
      const result = (column.validation as (v: any, r: RowData) => boolean | string)(val, rowData);
      if (result === false) {
        return { 
          valid: false, 
          message: column.validationMessage || 'Invalid value' 
        };
      }
      if (typeof result === 'string') {
        return { valid: false, message: result };
      }
    }

    return { valid: true };
  };

  // Handle save
  const handleSave = async () => {
    const validationResult = validate(value);
    
    if (!validationResult.valid) {
      setError(validationResult.message || 'Invalid value');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await onSave(value);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
      setIsLoading(false);
    }
  };

  // Handle cancel
  const handleCancel = () => {
    setValue(initialValue);
    setError(null);
    onCancel();
  };

  // Handle keyboard events
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && column.type !== 'longtext') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      handleSave();
      // Tab navigation will be handled by parent component
    }
  };

  // Click outside to save
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        handleSave();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [value]);

  // Base editor styles
  const containerStyle: React.CSSProperties = {
    borderBottom: `1px solid ${t.border}`,
    borderRight: `1px solid ${t.border}`,
    backgroundColor: t.bgInputFocus,
  };

  const inputBaseStyle: React.CSSProperties = {
    backgroundColor: t.bgInput,
    border: error ? `2px solid ${t.red}` : `1px solid ${t.borderFocus}`,
    color: t.text,
  };

  return (
    <div 
      ref={containerRef}
      className={styles.container}
      style={containerStyle}
      onKeyDown={handleKeyDown}
      role="cell"
      aria-label={`Editing ${column.label}`}
    >
      {/* Render children or default input */}
      {children ? (
        React.cloneElement(children as React.ReactElement, {
          value,
          onChange: setValue,
          className: styles.inputBase,
          style: inputBaseStyle,
          autoFocus: true,
          disabled: isLoading,
        })
      ) : (
        <input
          type="text"
          value={value ?? ''}
          onChange={(e) => setValue(e.target.value)}
          className={styles.inputBase}
          style={inputBaseStyle}
          autoFocus
          disabled={isLoading}
        />
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div
          className={styles.loadingSpinner}
          style={{
            border: `2px solid ${t.border}`,
            borderTop: `2px solid ${t.accent}`,
          }}
        />
      )}

      {/* Error message */}
      {error && (
        <div
          className={styles.errorMessage}
          style={{
            backgroundColor: t.redBg,
            border: `1px solid ${t.red}`,
            color: t.red,
          }}
          role="alert"
        >
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};

/**
 * Hook to provide common editor functionality
 */
export const useEditorState = (initialValue: any) => {
  const [value, setValue] = useState(initialValue);
  const [isDirty, setIsDirty] = useState(false);

  const handleChange = (newValue: any) => {
    setValue(newValue);
    setIsDirty(true);
  };

  const reset = () => {
    setValue(initialValue);
    setIsDirty(false);
  };

  return {
    value,
    setValue: handleChange,
    isDirty,
    reset,
  };
};
