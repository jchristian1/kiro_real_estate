import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '../contexts/ToastContext';
import { useT } from '../utils/useT';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const PAGE_SIZE = 20;

interface Company { id: number; name: string; phone: string | null; email: string | null; created_at: string; }
interface FormState { name: string; phone: string; email: string; }
const emptyForm: FormState = { name: '', phone: '', email: '' };

export const CompaniesPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const t = useT();
  const [companies, setCompanies] = useState<Company[]>([]);
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

  useEffect(() => { fetchCompanies(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm); setFormError(null); setShowForm(true); };
  const openEdit = (c: Company) => { setEditing(c); setForm({ name: c.name, phone: c.phone ?? '', email: c.email ?? '' }); setFormError(null); setShowForm(true); };

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
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: t.text, letterSpacing: '-0.5px' }}>Companies</span>
        <button onClick={openCreate} style={t.btnPrimary}>Add Company</button>
      </div>

      {/* Inline form */}
      {showForm && (
        <div style={{ ...t.card, marginBottom: 20, maxWidth: 520 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 18 }}>
            {editing ? 'Edit Company' : 'New Company'}
          </div>
          <form onSubmit={handleSubmit}>
            {formError && (
              <div style={{ padding: '10px 14px', background: t.redBg, border: `1px solid ${t.red}30`, borderRadius: 9, fontSize: 13, color: t.red, marginBottom: 14 }}>
                {formError}
              </div>
            )}
            {[
              { key: 'name' as const, label: 'Name *', type: 'text', placeholder: 'Company name' },
              { key: 'phone' as const, label: 'Phone', type: 'tel', placeholder: '555-123-4567' },
              { key: 'email' as const, label: 'Email', type: 'email', placeholder: 'contact@company.com' },
            ].map(f => (
              <div key={f.key} style={{ marginBottom: 14 }}>
                <label style={t.labelStyle}>{f.label}</label>
                <input type={f.type} value={form[f.key]} placeholder={f.placeholder}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  style={inputStyle}
                  onFocus={e => (e.target.style.borderColor = t.borderFocus)}
                  onBlur={e => (e.target.style.borderColor = t.border)} />
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
              <button type="button" onClick={() => setShowForm(false)} disabled={submitting} style={t.btnSecondary}>Cancel</button>
              <button type="submit" disabled={submitting} style={{ ...t.btnPrimary, opacity: submitting ? 0.6 : 1 }}>
                {submitting ? 'Saving…' : editing ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: t.textFaint, fontSize: 14 }}>Loading…</div>
      ) : companies.length === 0 ? (
        <div style={{ ...t.card, textAlign: 'center', padding: 60, color: t.textFaint }}>No companies yet</div>
      ) : (
        <>
          <div style={t.card}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  {['Name', 'Phone', 'Email', 'Created', 'Actions'].map(h => (
                    <th key={h} style={{ ...t.th, textAlign: h === 'Actions' ? 'right' : 'left' }}>{h}</th>
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                style={{ ...t.btnSecondary, opacity: page === 1 ? 0.4 : 1 }}>Previous</button>
              <span style={{ fontSize: 13, color: t.textMuted }}>Page {page} of {Math.ceil(companies.length / PAGE_SIZE)}</span>
              <button onClick={() => setPage(p => Math.min(Math.ceil(companies.length / PAGE_SIZE), p + 1))} disabled={page === Math.ceil(companies.length / PAGE_SIZE)}
                style={{ ...t.btnSecondary, opacity: page === Math.ceil(companies.length / PAGE_SIZE) ? 0.4 : 1 }}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
