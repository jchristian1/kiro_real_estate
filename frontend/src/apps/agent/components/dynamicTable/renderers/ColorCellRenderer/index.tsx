import React from 'react';
import { CellRenderer, CellRendererProps } from '../CellRenderer';

/**
 * ColorCellRenderer
 * 
 * Renders colored cells with:
 * - Background color from cell value
 * - Auto-calculated text color (black/white) for contrast
 * - Hex value in tooltip
 * - Theme-integrated styling
 * 
 * Requirements: 9.1, 9.5
 */
export const ColorCellRenderer: React.FC<CellRendererProps> = (props) => {
  const { value } = props;
  
  // Handle null/undefined
  if (!value) {
    return <CellRenderer {...props}>—</CellRenderer>;
  }
  
  // Calculate luminance to determine text color
  const getLuminance = (hexColor: string): number => {
    // Remove # if present
    const hex = hexColor.replace('#', '');
    
    // Convert to RGB
    const r = parseInt(hex.substr(0, 2), 16) / 255;
    const g = parseInt(hex.substr(2, 2), 16) / 255;
    const b = parseInt(hex.substr(4, 2), 16) / 255;
    
    // Calculate relative luminance
    const [rs, gs, bs] = [r, g, b].map(c => {
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
  };
  
  // Determine text color based on background luminance
  const luminance = getLuminance(value);
  const textColor = luminance > 0.5 ? '#000000' : '#ffffff';
  
  return (
    <CellRenderer 
      {...props}
      column={{
        ...props.column,
        cellStyle: (val: any, rowData: any) => {
          const customStyle = props.column.cellStyle 
            ? (props.column.cellStyle as (v: any, r: any) => React.CSSProperties)(val, rowData)
            : {};
          return {
            ...customStyle,
            backgroundColor: value,
            color: textColor,
          };
        },
      }}
    >
      <span title={`Color: ${value}`}>
        {value}
      </span>
    </CellRenderer>
  );
};
