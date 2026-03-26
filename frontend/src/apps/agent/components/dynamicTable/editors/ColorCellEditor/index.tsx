import React, { useState } from 'react';
import { HexColorPicker } from 'react-colorful';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { getTokens } from '@/shared/utils/theme';
import { CellEditorProps } from '../CellEditor';
import { ColorColumnConfig } from '../../types';
import styles from './index.module.css';

/**
 * ColorCellEditor
 * 
 * Renders color picker with:
 * - Preset colors from config
 * - Custom color picker
 * - Immediate persistence on selection
 * - Hex color display
 * 
 * Requirements: 9.2, 9.3, 9.4
 */
export const ColorCellEditor: React.FC<CellEditorProps> = ({
  value: initialValue,
  column,
  onSave,
  onCancel,
}) => {
  const { theme } = useTheme();
  const t = getTokens(theme);
  const colorColumn = column as ColorColumnConfig;
  const [color, setColor] = useState(initialValue || '#6366f1');

  const handleColorSelect = (selectedColor: string) => {
    setColor(selectedColor);
    onSave(selectedColor);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      onSave(color);
    }
  };

  // Default color presets if not provided
  const defaultPresets = [
    { value: '#ef4444', label: 'Red' },
    { value: '#f97316', label: 'Orange' },
    { value: '#eab308', label: 'Yellow' },
    { value: '#22c55e', label: 'Green' },
    { value: '#3b82f6', label: 'Blue' },
    { value: '#6366f1', label: 'Indigo' },
    { value: '#a855f7', label: 'Purple' },
    { value: '#ec4899', label: 'Pink' },
  ];

  const presets = colorColumn.colorOptions || defaultPresets;

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
      {/* Color picker */}
      <div className={styles.pickerWrapper}>
        <HexColorPicker color={color} onChange={setColor} />
      </div>

      {/* Hex input */}
      <input
        type="text"
        className={styles.hexInput}
        value={color}
        onChange={(e) => setColor(e.target.value)}
        placeholder="#000000"
        autoFocus
        style={{
          backgroundColor: t.bgInput,
          border: `1px solid ${t.borderFocus}`,
          color: t.text,
        }}
      />

      {/* Preset colors */}
      <div className={styles.presetsLabel} style={{ color: t.textMuted }}>
        Presets:
      </div>
      <div className={styles.presetsGrid}>
        {presets.map((preset, index) => (
          <button
            key={index}
            className={styles.presetButton}
            onClick={() => handleColorSelect(preset.value)}
            title={preset.label}
            style={{
              backgroundColor: preset.value,
              border: color === preset.value ? `3px solid ${t.accent}` : `1px solid ${t.border}`,
            }}
          />
        ))}
      </div>

      {/* Instructions */}
      <div
        className={styles.hint}
        style={{
          color: t.textMuted,
        }}
      >
        Press Enter to save, Escape to cancel
      </div>
    </div>
  );
};
