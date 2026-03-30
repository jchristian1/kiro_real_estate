import React from "react";
import { MockLead } from "../../mockData";
import { useT } from "@/shared/hooks/useT";
import { ConfigurableDrawer } from "../ConfigurableDrawer";
import styles from "../../index.module.css";

interface LeadsLawDrawerProps {
  lead: MockLead | null;
  onClose: () => void;
  onSave: (updatedLead: Partial<MockLead>) => void;
}

export const LeadsLawDrawer: React.FC<LeadsLawDrawerProps> = ({ lead, onClose, onSave }) => {
  const t = useT() as any;

  if (!lead) return null;

  const getStatusColor = (status: boolean | undefined) => status ? t.red : t.accent;
  const getStatusBg = (status: boolean | undefined) => status ? t.redBg : t.accentBg;

  // Custom function to render the header that was complex in the original Drawer
  const customHeaderRender = (leadData: MockLead, isEditing: boolean, formData: any, setFormData: any) => (
    <div style={{ ...t.card, display: 'flex', gap: 20, alignItems: 'center', padding: '24px' }}>
      <div className={styles.avatar} style={{ background: t.accentGrad, width: 64, height: 64, fontSize: 28 }}>
        {(leadData.full_name || "?")[0].toUpperCase()}
      </div>
      <div style={{ flex: 1 }}>
        {isEditing ? (
          <>
            <input
              value={formData.full_name || ''}
              onChange={e => setFormData({ ...formData, full_name: e.target.value })}
              style={{ ...t.input, width: '100%', marginBottom: 8, fontSize: 20, fontWeight: 700 }}
              placeholder="Full Name"
            />
            <input
              value={formData.email || ''}
              onChange={e => setFormData({ ...formData, email: e.target.value })}
              style={{ ...t.input, width: '100%', fontSize: 14 }}
              placeholder="Email Address"
            />
          </>
        ) : (
          <>
            <div style={{ fontSize: 22, fontWeight: 700, color: t.text, marginBottom: 4 }}>
              {leadData.full_name || "—"}
            </div>
            <div style={{ fontSize: 14, color: t.textMuted, display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
              {leadData.email || "—"}
            </div>
          </>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <span style={{
          display: 'inline-block',
          background: getStatusBg(leadData.has_eviction_lawsuit),
          color: getStatusColor(leadData.has_eviction_lawsuit),
          padding: '6px 14px',
          borderRadius: 20,
          fontSize: 13,
          fontWeight: 700
        }}>
          {leadData.has_eviction_lawsuit ? 'EVICTION FILED' : 'NO DEMAND'}
        </span>
        <div style={{ marginTop: 8, fontSize: 12, color: t.textFaint, fontWeight: 500 }}>
          Logged at: <br /> {leadData.time || "N/A"}
        </div>
      </div>
    </div>
  );

  return (
    <ConfigurableDrawer
      lead={lead}
      onClose={onClose}
      onSave={onSave}
      position="left"
      title="Lead Information"
      customHeaderRender={customHeaderRender}
      sections={[
        [
          {
            title: "Issue Description",
            icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>,
            fields: [
              {
                name: "issue_description",
                label: "Issue Description",
                type: "textarea",
                renderCustomView: (val: any) => (
                  <div style={{ background: t.bgHeader, borderLeft: `3px solid ${t.accent}`, padding: '16px', borderRadius: '0 8px 8px 0', color: t.text, fontSize: 15, lineHeight: 1.6, letterSpacing: '0.3px', height: '100%' }}>
                    {val || "No issue description provided."}
                  </div>
                )
              }
            ]
          },
          {
            title: "Contact Info & Address",
            columns: 1, // Changed to 1 since the parent card is already in a 2-column grid
            fields: [
              {
                name: "phone_number",
                label: "Phone Number",
                type: "text",
                renderCustomView: (val: any) => (
                  <div style={{ color: t.text, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={t.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                    {val || "—"}
                  </div>
                )
              },
              {
                name: "street_address",
                label: "Street Address",
                type: "text",
                renderCustomView: (val: any) => (
                  <div style={{ color: t.text, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={t.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    {val || "—"}
                  </div>
                )
              }
            ]
          }
        ],
        {
          title: "Case Assignment",
          fields: [
            {
              name: "has_eviction_lawsuit",
              label: "Active Eviction Lawsuit?",
              type: "checkbox",
              renderCustomView: (val) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px', background: val ? 'rgba(239, 68, 68, 0.1)' : 'rgba(0,0,0,0.02)', border: `1px solid ${val ? t.red : t.border}`, borderRadius: 8 }}>
                  <input type="checkbox" checked={!!val} readOnly style={{ width: 18, height: 18, accentColor: t.red, cursor: 'default' }} />
                  <span style={{ color: t.text, fontWeight: 600, fontSize: 14 }}>Active Eviction Lawsuit? {val ? "⚠️ SI" : "❌ NO"}</span>
                </div>
              ),
              renderCustomEdit: (val, onChange) => (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 8, cursor: 'pointer' }} onClick={() => onChange(!val)}>
                  <input type="checkbox" checked={!!val} onChange={(e) => onChange(e.target.checked)} onClick={(e) => e.stopPropagation()} style={{ width: 18, height: 18, accentColor: t.red, cursor: 'pointer' }} />
                  <span style={{ color: t.text, fontWeight: 600, fontSize: 14, userSelect: 'none' }}>Active Eviction Lawsuit?</span>
                </div>
              )
            }
          ]
        },
        {
          title: "Internal Comments",
          icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>,
          fields: [
            {
              name: "comments",
              label: "Internal Comments",
              type: "textarea",
              renderCustomView: (val: any) => (
                <div style={{ color: val ? t.text : t.textMuted, fontSize: 14, lineHeight: 1.5, padding: '12px', background: t.bgPage, border: `1px solid ${t.border}`, borderRadius: 6, fontStyle: val ? 'normal' : 'italic' }}>
                  {val || "No internal comments regarding this lead."}
                </div>
              )
            }
          ]
        }
      ]}
    />
  );
};

