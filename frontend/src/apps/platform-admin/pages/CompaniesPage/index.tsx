import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '@/shared/contexts/ToastContext';
import { useT } from '@/shared/hooks';
import { API_BASE_URL } from '@/shared/utils/config/enviroments';
import styles from './index.module.css';

const PAGE_SIZE = 20;

interface Company { id: number; name: string; phone: string | null; email: string | null; active_form_version_id: number | null; created_at: string; }
interface FormVersion { id: number; label: string; }
interface FormState { name: string; phone: string; email: string; active_form_version_id: number | null; }
const emptyForm: FormState = { name: '', phone: '', email: '', active_form_version_id: null };

export const CompaniesPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const t = useT();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [formVersions, setFormVersions] = useState<FormVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Company | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const fetchCompanies = async () => {
    try {
      const res = await axios.get<{ companies: Company[] }>(`${API_BASE_URL}/companies`);
      setCompanies(res.data.companies);
    } catch { toastError('Failed to load companies'); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchCompanies();
    axios.get<FormVersion[]>(`${API_BASE_URL}/buyer-leads/forms/versions/all`)
      .then(r => setFormVersions(r.data))
      .catch(err => console.error('Failed to load form versions:', err?.response?.status, err?.response?.data));
  }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm); setFormError(null); setShowForm(true); };
  const openEdit = (c: Company) => { setEditing(c); setForm({ name: c.name, phone: c.phone ?? '', email: c.email ?? '', active_form_version_id: c.active_form_version_id }); setFormError(null); setShowForm(true); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setFormError('Name is required'); return; }
    setSubmitting(true); setFormError(null);
    try {
      if (editing) { await axios.put(`${API_BASE_URL}/companies/${editing.id}`, form); success('Company updated'); }
      else { await axios.post(`${API_BASE_URL}/companies`, form); success('Company created'); }
      setShowForm(false); fetchCompanies();
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setFormError(e.response?.data?.message || 'Failed to save company');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (c: Company) => {
    if (!confirm(`Delete company "${c.name}"?`)) return;
    try { await axios.delete(`${API_BASE_URL}/companies/${c.id}`); setCompanies(p => p.filter(x => x.id !== c.id)); success('Deleted'); }
    catch { toastError('Failed to delete company'); }
  };

  const inputStyle = { ...t.input };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title} style={{ color: t.text }}>Companies</span>
        <button onClick={openCreate} style={t.btnPrimary}>Add Company</button>
      </div>

      {/* Inline form */}
      {showForm && (
        <div style={{ ...t.card, marginBottom: 20, maxWidth: 520 }}>
          <div className={styles.formTitle} style={{ color: t.text }}>
            {editing ? 'Edit Company' : 'New Company'}
          </div>
          <form onSubmit={handleSubmit}>
            {formError && (
              <div className={styles.errorAlert} style={{ background: t.redBg, border: `1px solid ${t.red}30`, color: t.red }}>
                {formError}
              </div>
            )}
            {[
              { key: 'name' as const, label: 'Name *', type: 'text', placeholder: 'Company name' },
              { key: 'phone' as const, label: 'Phone', type: 'tel', placeholder: '555-123-4567' },
              { key: 'email' as const, label: 'Email', type: 'email', placeholder: 'contact@company.com' },
            ].map(f => (
              <div key={f.key} className={styles.formField}>
                <label style={t.labelStyle}>{f.label}</label>
                <input type={f.type} value={form[f.key]} placeholder={f.placeholder}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  style={inputStyle}
                  onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                  onBlur={e => (e.target.style.borderColor = t.border)} />
              </div>
            ))}
            <div className={styles.formField}>
              <label style={t.labelStyle}>Qualification Form</label>
              <select
                value={form.active_form_version_id ?? ''}
                onChange={e => setForm(p => ({ ...p, active_form_version_id: e.target.value ? Number(e.target.value) : null }))}
                style={inputStyle}
              >
                <option value="">— No form assigned —</option>
                {formVersions.map(v => (
                  <option key={v.id} value={v.id}>{v.label}</option>
                ))}
              </select>
            </div>
            <div className={styles.formActions}>
              <button type="button" onClick={() => setShowForm(false)} disabled={submitting} style={t.btnSecondary}>Cancel</button>
              <button type="submit" disabled={submitting} style={{ ...t.btnPrimary, opacity: submitting ? 0.6 : 1 }}>
                {submitting ? 'Saving…' : editing ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className={styles.loadingContainer} style={{ color: t.textFaint }}>Loading…</div>
      ) : companies.length === 0 ? (
        <div style={{ ...t.card, ...{ textAlign: 'center', padding: 60 }, color: t.textFaint }}>No companies yet</div>
      ) : (
        <>
          <div style={t.card}>
            <table className={styles.table}>
              <thead>
                <tr>
                  {['Name', 'Phone', 'Email', 'Created', 'Actions'].map(h => (
                    <th key={h} style={t.th} className={h === 'Actions' ? styles.tableHeaderCellRight : styles.tableHeaderCell}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {companies.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((c, i) => (
                  <tr key={c.id} style={{ borderBottom: i < Math.min(PAGE_SIZE, companies.length - (page - 1) * PAGE_SIZE) - 1 ? `1px solid ${t.border}` : 'none' }}>
                    <td style={{ ...t.td, fontWeight: 600 }}>{c.name}</td>
                    <td style={{ ...t.td, color: t.textMuted }}>{c.phone || '—'}</td>
                    <td style={{ ...t.td, color: t.textMuted }}>{c.email || '—'}</td>
                    <td style={{ ...t.td, color: t.textMuted }}>{new Date(c.created_at).toLocaleDateString()}</td>
                    <td style={{ ...t.td, textAlign: 'right' }}>
                      <button onClick={() => openEdit(c)} style={{ ...t.btnSecondary, padding: '5px 12px', fontSize: 12, marginRight: 8 }}>Edit</button>
                      <button onClick={() => handleDelete(c)} style={{ ...t.btnDanger, padding: '5px 12px', fontSize: 12 }}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {Math.ceil(companies.length / PAGE_SIZE) > 1 && (
            <div className={styles.paginationContainer}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span className={styles.paginationText} style={{ color: t.textMuted }}>Page {page} of {Math.ceil(companies.length / PAGE_SIZE)}</span>
              <button onClick={() => setPage(p => Math.min(Math.ceil(companies.length / PAGE_SIZE), p + 1))} disabled={page === Math.ceil(companies.length / PAGE_SIZE)}
                style={{ ...t.btnSecondary, opacity: page === Math.ceil(companies.length / PAGE_SIZE) ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
