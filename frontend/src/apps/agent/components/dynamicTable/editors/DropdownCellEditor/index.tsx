import React, { useState, useEffect } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellEditorProps } from '../CellEditor';
import { DropdownColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * DropdownCellEditor
 * 
 * Renders dropdown with:
 * - String and object options support
 * - Immediate persistence on selection
 * - Async options loading
 * - Custom value support (allowCustom)
 * - Search functionality
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.6
 */
export const DropdownCellEditor: React.FC<CellEditorProps> = ({
  value: initialValue,
  column,
  onSave,
  onCancel,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const dropdownColumn = column as DropdownColumnConfig;
  const [options, setOptions] = useState(dropdownColumn.options || []);
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Load options if optionsLoader is provided
  useEffect(() => {
    if (dropdownColumn.optionsLoader) {
      setIsLoading(true);
      dropdownColumn.optionsLoader()
        .then(loadedOptions => {
          setOptions(loadedOptions);
          setIsLoading(false);
        })
        .catch(() => {
          setIsLoading(false);
        });
    }
  }, []);

  const handleSelect = (selectedValue: string) => {
    onSave(selectedValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  };

  // Filter options based on search
  const filteredOptions = options.filter(opt => {
    const label = typeof opt === 'string' ? opt : opt.label;
    return label.toLowerCase().includes(searchTerm.toLowerCase());
  });

  return (
    <div
      className={styles.container}
      style={{
        borderBottom: `1px solid ${t.border}`,
        borderRight: `1px solid ${t.border}`,
        backgroundColor: t.bgInputFocus,
      }}
      onKeyDown={handleKeyDown}
    >
      {/* Search input for allowCustom */}
      {dropdownColumn.allowCustom && (
        <input
          type="text"
          className={styles.searchInput}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && searchTerm) {
              handleSelect(searchTerm);
            }
          }}
          placeholder="Type or select..."
          autoFocus
          style={{
            backgroundColor: t.bgInput,
            border: `1px solid ${t.borderFocus}`,
            color: t.text,
          }}
        />
      )}

      {/* Options list */}
      <div
        className={styles.optionsList}
        style={{
          backgroundColor: t.bgCard,
          border: `1px solid ${t.border}`,
        }}
      >
        {isLoading ? (
          <div className={styles.optionsMessage} style={{ color: t.textMuted }}>
            Loading options...
          </div>
        ) : filteredOptions.length === 0 ? (
          <div className={styles.optionsMessage} style={{ color: t.textMuted }}>
            No options found
          </div>
        ) : (
          filteredOptions.map((opt, index) => {
            const optValue = typeof opt === 'string' ? opt : opt.value;
            const optLabel = typeof opt === 'string' ? opt : opt.label;
            const isSelected = optValue === initialValue;

            return (
              <div
                key={index}
                className={styles.option}
                onClick={() => handleSelect(optValue)}
                style={{
                  backgroundColor: isSelected ? t.accentBg : 'transparent',
                  color: isSelected ? t.accent : t.text,
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor = t.bgCardHover;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }
                }}
              >
                {optLabel}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
