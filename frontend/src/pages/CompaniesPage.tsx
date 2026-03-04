import React, { useEffect, useState } from 'react';
import axios, { AxiosError } from 'axios';
import { useToast } from '../contexts/ToastContext';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface Company {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  created_at: string;
}

interface FormState {
  name: string;
  phone: string;
  email: string;
}

const emptyForm: FormState = { name: '', phone: '', email: '' };

export const CompaniesPage: React.FC = () => {
  const { success, error: toastError } = useToast();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Company | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchCompanies = async () => {
    try {
      const res = await axios.get<{ companies: Company[] }>(`${API_BASE_URL}/companies`);
      setCompanies(res.data.companies);
    } catch {
      toastError('Failed to load companies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCompanies(); }, []);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormError(null);
    setShowForm(true);
  };

  const openEdit = (c: Company) => {
    setEditing(c);
    setForm({ name: c.name, phone: c.phone ?? '', email: c.email ?? '' });
    setFormError(null);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setFormError('Name is required'); return; }
    setSubmitting(true);
    setFormError(null);
    try {
      if (editing) {
        await axios.put(`${API_BASE_URL}/companies/${editing.id}`, form);
        success('Company updated');
      } else {
        await axios.post(`${API_BASE_URL}/companies`, form);
        success('Company created');
      }
      setShowForm(false);
      fetchCompanies();
    } catch (err) {
      const e = err as AxiosError<{ message?: string }>;
      setFormError(e.response?.data?.message || 'Failed to save company');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (c: Company) => {
    if (!confirm(`Delete company "${c.name}"?`)) return;
    try {
      await axios.delete(`${API_BASE_URL}/companies/${c.id}`);
      setCompanies((prev) => prev.filter((x) => x.id !== c.id));
      success('Company deleted');
    } catch {
      toastError('Failed to delete company');
    }
  };

  const inputClass = 'w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Companies</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md">
          Add Company
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow p-6 max-w-lg">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">{editing ? 'Edit Company' : 'New Company'}</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {formError && <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm">{formError}</div>}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name <span className="text-red-500">*</span></label>
              <input type="text" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className={inputClass} placeholder="Company name" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input type="tel" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                className={inputClass} placeholder="555-123-4567" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                className={inputClass} placeholder="contact@company.com" />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowForm(false)} disabled={submitting}
                className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50">
                Cancel
              </button>
              <button type="submit" disabled={submitting}
                className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
                {submitting ? 'Saving...' : editing ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32 text-gray-500">Loading...</div>
      ) : companies.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">No companies yet</div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {companies.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{c.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{c.phone || '—'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{c.email || '—'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{new Date(c.created_at).toLocaleDateString()}</td>
                  <td className="px-6 py-4 text-right text-sm space-x-3">
                    <button onClick={() => openEdit(c)} className="text-gray-600 hover:text-gray-900">Edit</button>
                    <button onClick={() => handleDelete(c)} className="text-red-600 hover:text-red-900">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
