import React, { useState, useEffect } from "react";
import { MockLead } from "../../mockData";
import { useT } from "@/shared/hooks/useT";
import styles from "./index.module.css";

export type FieldConfig = {
  name: keyof MockLead;
  label: string;
  type: "text" | "number" | "select" | "checkbox" | "textarea" | "link" | "custom";
  options?: string[]; // for select
  renderCustomView?: (value: any, lead: MockLead, t: any) => React.ReactNode; // custom render when not editing
  renderCustomEdit?: (value: any, onChange: (v: any) => void, t: any) => React.ReactNode; // custom edit field
  colSpan?: number; // to span columns
};

export type SectionConfig = {
  title?: string;
  icon?: React.ReactNode;
  fields: FieldConfig[];
  columns?: number; // e.g. 1 or 2
};

export interface ConfigurableDrawerProps {
  lead: MockLead | null;
  onClose: () => void;
  onSave: (updatedLead: Partial<MockLead>) => void;
  position: "left" | "right";
  title: string;
  sections: (SectionConfig | SectionConfig[])[];
  customHeaderRender?: (lead: MockLead, isEditing: boolean, formData: Partial<MockLead>, setFormData: any, t: any) => React.ReactNode;
}

export const ConfigurableDrawer: React.FC<ConfigurableDrawerProps> = ({
  lead,
  onClose,
  onSave,
  position,
  title,
  sections,
  customHeaderRender
}) => {
  const t = useT() as any;
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<Partial<MockLead>>({});

  useEffect(() => {
    if (lead) {
      setFormData(lead);
      setIsEditing(false); // Reset to view mode when lead changes
    }
  }, [lead]);

  if (!lead) return null;

  const handleSave = () => {
    onSave(formData);
    setIsEditing(false);
  };

  const overlayClass = position === "left" ? styles.drawerOverlay : styles.drawerOverlayRight;
  const drawerClass = position === "left" ? styles.sideDrawer : styles.sideDrawerRight;

  return (
    <div className={overlayClass} onClick={onClose}>
      <div
        className={drawerClass}
        style={{ background: t.bgPage }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* HEADER */}
        <div
          className={styles.drawerHeader}
          style={{ background: t.bgHeader, borderColor: t.border, padding: '16px 24px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              className={styles.detailTitle}
              style={{ color: t.text, margin: 0, textAlign: 'left', fontSize: 18, fontWeight: 700 }}
            >
              {title}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={() => isEditing ? handleSave() : setIsEditing(true)}
              className={styles.editToggleBtn}
              style={{
                color: isEditing ? '#fff' : t.text,
                borderColor: t.border,
                background: isEditing ? t.green : 'transparent',
                transition: 'all 0.2s ease',
              }}
            >
              {isEditing ? 'Save Changes' : 'Update Info'}
            </button>
            <button
              onClick={onClose}
              className={styles.closeBtn}
              style={{ color: t.text, fontSize: 24 }}
            >
              &times;
            </button>
          </div>
        </div>

        {/* BODY */}
        <div className={styles.detailContent} style={{ padding: '24px' }}>

          {/* Custom Header Injection (like the Identity Box) */}
          {customHeaderRender && (
            <div style={{ marginBottom: 20 }}>
              {customHeaderRender(lead, isEditing, formData, setFormData, t)}
            </div>
          )}

          {/* Render Sections Data-Driven */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {sections.map((sectionItem, rowIdx) => {
              const rowSections = Array.isArray(sectionItem) ? sectionItem : [sectionItem];
              const isMultiCol = rowSections.length > 1;

              return (
                <div key={rowIdx} style={{ display: isMultiCol ? 'grid' : 'block', gridTemplateColumns: isMultiCol ? `repeat(${rowSections.length}, 1fr)` : '1fr', gap: 20 }}>
                  {rowSections.map((section, colIdx) => (
                    <div key={colIdx} style={{ ...t.card, padding: 24 }}>
                      {section.title && (
                        <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                          {section.icon}
                          {section.title}
                        </div>
                      )}

                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: section.columns ? `repeat(${section.columns}, 1fr)` : '1fr',
                        gap: 20
                      }}>
                        {section.fields.map((field) => {
                          const value = isEditing ? (formData[field.name] ?? lead[field.name]) : lead[field.name];

                          return (
                            <div key={field.name} style={{ gridColumn: field.colSpan ? `span ${field.colSpan}` : 'auto' }}>
                              {field.type !== "checkbox" && (
                                <div style={{ fontSize: 12, color: t.textFaint, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
                                  {field.label}
                                </div>
                              )}

                              {isEditing ? (
                                field.renderCustomEdit ? field.renderCustomEdit(value, (val) => setFormData({ ...formData, [field.name]: val }), t) :
                                  field.type === "text" || field.type === "link" ? (
                                    <input
                                      value={(value as string) || ''}
                                      onChange={e => setFormData({ ...formData, [field.name]: e.target.value })}
                                      style={{ ...t.input, width: '100%', padding: '6px 10px' }}
                                    />
                                  ) : field.type === "number" ? (
                                    <input
                                      type="number"
                                      value={(value as number) || ''}
                                      onChange={e => setFormData({ ...formData, [field.name]: parseFloat(e.target.value) || null })}
                                      style={{ ...t.input, width: '100%', padding: '6px 10px' }}
                                    />
                                  ) : field.type === "textarea" ? (
                                    <textarea
                                      value={(value as string) || ''}
                                      onChange={e => setFormData({ ...formData, [field.name]: e.target.value })}
                                      style={{ ...t.input, width: '100%', padding: '12px', minHeight: 80, resize: 'vertical', fontSize: 14 }}
                                    />
                                  ) : field.type === "select" ? (
                                    <select
                                      value={(value as string) || ''}
                                      onChange={e => setFormData({ ...formData, [field.name]: e.target.value })}
                                      style={{ ...t.input, width: '100%', padding: '6px 10px', backgroundColor: t.bgPage }}
                                    >
                                      <option value="">Select...</option>
                                      {field.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                      {value && !field.options?.includes(value as string) && (
                                        <option value={value as string}>{value as string}</option>
                                      )}
                                    </select>
                                  ) : field.type === "checkbox" ? (
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: t.text, fontWeight: 500, cursor: 'pointer' }}>
                                      <input
                                        type="checkbox"
                                        checked={!!value}
                                        onChange={e => setFormData({ ...formData, [field.name]: e.target.checked })}
                                        style={{ width: 18, height: 18, accentColor: t.green }}
                                      />
                                      {field.label}
                                    </label>
                                  ) : null
                              ) : (
                                field.renderCustomView ? field.renderCustomView(value, lead, t) :
                                  field.type === "checkbox" ? (
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: t.text, fontWeight: 500 }}>
                                      <input
                                        type="checkbox"
                                        checked={!!value}
                                        disabled
                                        style={{ width: 18, height: 18, accentColor: t.green }}
                                      />
                                      {field.label}
                                    </label>
                                  ) : field.type === "link" ? (
                                    value ? (
                                      <a href={value as string} target="_blank" rel="noreferrer" style={{ display: 'block', background: t.accentBg, color: t.accent, padding: '8px 12px', borderRadius: 6, fontSize: 14, wordBreak: 'break-all', textDecoration: 'none' }}>
                                        {(value as string)}
                                      </a>
                                    ) : <div style={{ color: t.textMuted, fontSize: 14, fontStyle: 'italic' }}>—</div>
                                  ) : (
                                    <div style={{ color: t.text, fontWeight: field.type === "textarea" ? 400 : 500, whiteSpace: field.type === "textarea" ? 'pre-wrap' : 'normal', lineHeight: field.type === "textarea" ? 1.6 : 1.2 }}>
                                      {(value !== null && value !== undefined && value !== '') ? String(value) : "—"}
                                    </div>
                                  )
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
