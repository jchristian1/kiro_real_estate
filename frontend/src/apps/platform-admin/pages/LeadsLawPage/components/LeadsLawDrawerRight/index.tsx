import React from "react";
import { MockLead } from "../../mockData";
import { useT } from "@/shared/hooks/useT";
import { ConfigurableDrawer } from "../ConfigurableDrawer";
export const getTextedStatusColor = (val: string, t: any) => {
  const s = val?.toUpperCase() || '';
  if (s.includes('TEXT K') || s.includes('TEXT J') || s.includes('TEXT H')) return { bg: t.greenBg, color: t.green };
  if (s.includes('YLP')) return { bg: '#ffedcc', color: '#cc7700' };
  if (s.includes('CURRENT')) return { bg: '#fff5cc', color: '#997700' };
  if (s.includes('NO TEXT')) return { bg: t.bgBadge, color: t.textMuted };
  if (s.includes('🔴') || s.includes('ERROR') || s.includes('INVALID')) return { bg: t.redBg, color: t.red };
  return { bg: t.bgBadge, color: t.textSecondary };
};

export const getCalledStatusColor = (val: string, t: any) => {
  const s = val?.toUpperCase() || '';
  if (s.includes('VOICE')) return { bg: t.greenBg, color: t.green };
  if (s.includes('NO ANSWER') || s.includes('WRONG NUMBER')) return { bg: t.redBg, color: t.red };
  if (s.includes('BUSY')) return { bg: '#ffedcc', color: '#cc7700' };
  return { bg: t.bgBadge, color: t.textSecondary };
};

interface LeadsLawDrawerRightProps {
  lead: MockLead | null;
  onClose: () => void;
  onSave: (updatedLead: Partial<MockLead>) => void;
}

export const LeadsLawDrawerRight: React.FC<LeadsLawDrawerRightProps> = ({ lead, onClose, onSave }) => {
  const t = useT() as any;

  if (!lead) return null;

  const textedOptions = [
    "TEXT Justin", "TEXT Haley", "TEXT Kyla", "TEXT Kian",
    "🔴", "YLP AUTO TEXT", "NO TEXT NECESSARY", "CURRENT CLIENT"
  ];

  const calledOptions = [
    "VOICE CALL", "VOICE CALL MESSAGED", "NO ANSWER", "BUSY", "WRONG NUMBER"
  ];

  const handoffOptions = [
    "JUSTIN", "HALEY", "KYLA", "KIAN", "MEHER"
  ];

  return (
    <ConfigurableDrawer
      lead={lead}
      onClose={onClose}
      onSave={onSave}
      position="right"
      title="Status & Tracking"
      sections={[
        {
          columns: 2,
          fields: [
            // Left Column: Communication
            {
              name: "called_status", // Placeholder for grouping logic, we can put them in the same section
              label: "Called Status",
              type: "select",
              options: calledOptions,
              renderCustomView: (val) => (
                <div style={{ color: t.text, fontWeight: 500 }}>
                  {val ? (
                    <span style={{ display: 'inline-block', padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 600, ...getCalledStatusColor(val as string, t) }}>
                      {val as string}
                    </span>
                  ) : "—"}
                </div>
              )
            },
            // Right Column part 1: Assignment
            {
              name: "handoff_to",
              label: "Handoff To",
              type: "select",
              options: handoffOptions,
              renderCustomView: (val: any) => (
                <div style={{ color: t.text, fontWeight: 500 }}>
                  {val ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: t.bgPage, border: `1px solid ${t.border}`, padding: '4px 10px', borderRadius: 20, fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>
                      <div style={{ width: 8, height: 8, background: t.green, borderRadius: '50%' }} /> {(val as string).toLowerCase()}
                    </span>
                  ) : "Unassigned"}
                </div>
              )
            },
            // Left Column: Communication 2
            {
              name: "texted_status",
              label: "Texted Status",
              type: "select",
              options: textedOptions,
              renderCustomView: (val: any) => (
                <div style={{ color: t.text, fontWeight: 500 }}>
                  {val ? (
                    <span style={{ display: 'inline-block', padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 600, ...getTextedStatusColor(val as string, t) }}>
                      {val as string}
                    </span>
                  ) : "—"}
                </div>
              )
            },
            // Right Column part 2
            {
              name: "retainer_amount",
              label: "Retainer Amount",
              type: "number",
              renderCustomView: (val: any) => (
                <div style={{ color: t.green, fontWeight: 700, fontSize: 18 }}>
                  {val ? `$${val}` : "—"}
                </div>
              )
            },
            {
              name: "signed",
              label: "Client Agreement Signed",
              type: "checkbox",
              colSpan: 2, // It will just go next or span
              renderCustomView: (val) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px', background: val ? 'rgba(34, 197, 94, 0.1)' : 'rgba(0,0,0,0.02)', border: `1px solid ${val ? t.green : t.border}`, borderRadius: 8 }}>
                  <input type="checkbox" checked={!!val} readOnly style={{ width: 18, height: 18, accentColor: t.green, cursor: 'default' }} />
                  <span style={{ color: t.text, fontWeight: 600, fontSize: 14 }}>Client Agreement Signed {val ? "✅" : "❌"}</span>
                </div>
              ),
              renderCustomEdit: (val, onChange) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 8, cursor: 'pointer' }} onClick={() => onChange(!val)}>
                  <input type="checkbox" checked={!!val} onChange={(e) => onChange(e.target.checked)} onClick={(e) => e.stopPropagation()} style={{ width: 18, height: 18, accentColor: t.green, cursor: 'pointer' }} />
                  <span style={{ color: t.text, fontWeight: 600, fontSize: 14 }}>Client Agreement Signed</span>
                </div>
              )
            }
          ]
        },
        {
          title: "NYSCEF Document Link",
          icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>,
          fields: [
            {
              name: "nyscef_link",
              label: "NYSCEF Link",
              type: "link"
            }
          ]
        },
        {
          title: "Follow Up Notes",
          fields: [
            {
              name: "followed_up_notes",
              label: "Follow Up Notes",
              type: "textarea",
              renderCustomView: (val: any) => (
                <div style={{ color: t.textSecondary, fontSize: 14, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{val || "—"}</div>
              )
            }
          ]
        }
      ]}
    />
  );
};
