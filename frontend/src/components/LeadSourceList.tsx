/**
 * LeadSourceList Component
 *
 * Displays a table of lead sources with name, regex pattern (truncated),
 * description, created date, and action buttons.
 *
 * Requirements: 2.1
 */

import React from 'react';

export interface LeadSource {
  id: number;
  sender_email: string;
  identifier_snippet: string;
  name_regex: string;
  phone_regex: string;
  template_id: number | null;
  auto_respond_enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface LeadSourceListProps {
  leadSources: LeadSource[];
  onEdit: (leadSource: LeadSource) => void;
  onDelete: (leadSource: LeadSource) => void;
  onView: (leadSource: LeadSource) => void;
  onViewHistory?: (leadSource: LeadSource) => void;
}

export const LeadSourceList: React.FC<LeadSourceListProps> = ({
  leadSources,
  onEdit,
  onDelete,
  onView,
  onViewHistory,
}) => {
  const truncate = (str: string, maxLen = 40): string =>
    str.length > maxLen ? str.slice(0, maxLen) + '…' : str;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Sender Email
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Identifier Snippet
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Name Regex
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Auto Respond
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Created
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {leadSources.map((ls) => (
            <tr key={ls.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm font-medium text-gray-900">{ls.sender_email}</div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-500">{truncate(ls.identifier_snippet)}</div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <code
                  className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded font-mono"
                  title={ls.name_regex}
                >
                  {truncate(ls.name_regex)}
                </code>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                  ls.auto_respond_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {ls.auto_respond_enabled ? 'Yes' : 'No'}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm text-gray-500">
                  {new Date(ls.created_at).toLocaleDateString()}
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button
                  className="text-blue-600 hover:text-blue-900 mr-4"
                  onClick={() => onView(ls)}
                >
                  View
                </button>
                <button
                  className="text-gray-600 hover:text-gray-900 mr-4"
                  onClick={() => onEdit(ls)}
                >
                  Edit
                </button>
                {onViewHistory && (
                  <button
                    className="text-purple-600 hover:text-purple-900 mr-4"
                    onClick={() => onViewHistory(ls)}
                  >
                    History
                  </button>
                )}
                <button
                  className="text-red-600 hover:text-red-900"
                  onClick={() => onDelete(ls)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
