import React, { useState, useRef, useEffect } from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellEditorProps } from '../CellEditor';
import { LongTextColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * LongTextCellEditor
 * 
 * Renders textarea with:
 * - Auto-expanding height up to maxHeight
 * - Character counter for maxLength
 * - Ctrl+Enter or blur to save
 * - Escape to cancel
 * 
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.6
 */
export const LongTextCellEditor: React.FC<CellEditorProps> = ({
  value: initialValue,
  column,
  onSave,
  onCancel,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const longTextColumn = column as LongTextColumnConfig;
  const [value, setValue] = useState(initialValue ?? '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const maxHeight = longTextColumn.maxHeight || 200;
  const maxLength = longTextColumn.maxLength;
  const remainingChars = maxLength ? maxLength - value.length : null;

  // Auto-expand textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, maxHeight);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [value, maxHeight]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      onSave(value);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  };

  const handleBlur = () => {
    onSave(value);
  };

  return (
    <div
      className={styles.container}
      style={{
        borderBottom: `1px solid ${t.border}`,
        borderRight: `1px solid ${t.border}`,
        backgroundColor: t.bgInputFocus,
      }}
    >
      <textarea
        ref={textareaRef}
        className={styles.textarea}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        maxLength={maxLength}
        placeholder={longTextColumn.placeholder}
        autoFocus
        style={{
          backgroundColor: t.bgInput,
          border: `1px solid ${t.borderFocus}`,
          color: t.text,
          maxHeight: `${maxHeight}px`,
        }}
      />
      
      {/* Character counter */}
      {maxLength && (
        <div
          className={styles.charCounter}
          style={{
            color: remainingChars && remainingChars < 0 ? t.red : t.textMuted,
          }}
        >
          {remainingChars !== null && `${remainingChars} characters remaining`}
        </div>
      )}
      
      <div
        className={styles.hint}
        style={{
          color: t.textMuted,
        }}
      >
        Press Ctrl+Enter to save, Escape to cancel
      </div>
    </div>
  );
};
