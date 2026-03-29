import React, { useState } from "react";
import { MockLead, mockLeadsData } from "./mockData";
import { useT } from "@/shared/hooks/useT";
import { LeadsLawTable, LeadsLawDrawer, LeadsLawDrawerRight } from "./components";
import styles from "./index.module.css";
import { useToast } from "@/shared/contexts/ToastContext";

export const LeadsLawPage: React.FC = () => {
  const t = useT();
  const { success } = useToast();

  // Usamos el mock data como estado inicial para poder editarlo visualmente
  const [leads, setLeads] = useState<MockLead[]>(mockLeadsData);
  const [selectedLeadLeft, setSelectedLeadLeft] = useState<MockLead | null>(null);
  const [selectedLeadRight, setSelectedLeadRight] = useState<MockLead | null>(null);

  const handleSaveLead = (updatedData: Partial<MockLead>, id: string) => {
    // Actualizamos el mock en memoria
    setLeads(current => current.map(lead =>
      lead.id === id ? { ...lead, ...updatedData } : lead
    ));

    // Update active drawers
    if (selectedLeadLeft?.id === id) {
      setSelectedLeadLeft(prev => prev ? { ...prev, ...updatedData } : null);
    }
    if (selectedLeadRight?.id === id) {
      setSelectedLeadRight(prev => prev ? { ...prev, ...updatedData } : null);
    }
    success("Lead (mock) updated successfully!");
  };

  return (
    <div className={styles.mainWrapper}>
      {/* Drawer Derecho (Status) */}
      <LeadsLawDrawerRight
        lead={selectedLeadRight}
        onClose={() => setSelectedLeadRight(null)}
        onSave={(data) => selectedLeadRight && handleSaveLead(data, selectedLeadRight.id)}
      />

      {/* Drawer Izquierdo (Info) */}
      <LeadsLawDrawer
        lead={selectedLeadLeft}
        onClose={() => setSelectedLeadLeft(null)}
        onSave={(data) => selectedLeadLeft && handleSaveLead(data, selectedLeadLeft.id)}
      />

      {/* Cabecera */}
      <div className={styles.headerFlex}>
        <h1 className={styles.headerTitle} style={{ color: t.text }}>
          Law Leads {" "}
          <span className={styles.headerCount} style={{ color: t.textMuted }}>
            ({leads.length} mocked)
          </span>
        </h1>
        <div className={styles.headerActions}>
          {/* Aquí irían botones adicionales, exportación, etc */}
        </div>
      </div>

      {/* Componente de la Tabla Modularizada */}
      <div style={{ marginTop: 20 }}>
        <LeadsLawTable
          data={leads}
          onSelectLeadLeft={setSelectedLeadLeft}
          onSelectLeadRight={setSelectedLeadRight}
          activeLeadIdLeft={selectedLeadLeft?.id || null}
          activeLeadIdRight={selectedLeadRight?.id || null}
        />
      </div>
    </div>
  );
};

export default LeadsLawPage;
