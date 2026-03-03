/**
 * TemplateList Component
 * Requirements: 3.1
 */
import React from 'react';

export interface Template {
  id: number;
  name: string;
  subject: string;
  body: string;
  created_at: string;
  updated_at: string;
}

interface TemplateListProps {
  templates: Template[];
  onEdit: (t: Template) => void;
  onDelete: (t: Template) => void;
  onViewHistory: (t: Template) => void;
}

export const TemplateList: React.FC<TemplateListProps> = ({ templates, onEdit, onDelete, onViewHistory }) => {
  const truncate = (s: string, n = 60) => s.length > n ? s.slice(0, n) + '…' : s;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {['Name', 'Subject', 'Updated', 'Actions'].map((h) => (
              <th key={h} className={`px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider${h === 'Actions' ? ' text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {templates.map((t) => (
            <tr key={t.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{t.name}</td>
              <td className="px-6 py-4 text-sm text-gray-500">{truncate(t.subject)}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(t.updated_at).toLocaleDateString()}</td>
              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                <button className="text-gray-600 hover:text-gray-900" onClick={() => onEdit(t)}>Edit</button>
                <button className="text-purple-600 hover:text-purple-900" onClick={() => onViewHistory(t)}>History</button>
                <button className="text-red-600 hover:text-red-900" onClick={() => onDelete(t)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
