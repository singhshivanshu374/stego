import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { CheckCircle2, AlertCircle } from 'lucide-react';

interface Operation {
  operation_id: string;
  operation_type: string;
  mode: string;
  image_filename: string;
  status: string;
  created_at: string;
}

export function RecentActivityTable() {
  const [operations, setOperations] = useState<Operation[]>([]);
  const [loading, setLoading] = useState(true);

  const isSuccessfulStatus = (status: string) =>
    ['success', 'completed'].includes(status.toLowerCase());

  const fetchOperations = async () => {
    try {
      const data = await api.getRecentOperations();
      setOperations(data);
    } catch (err) {
      console.error("Failed to fetch recent operations", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperations();
  }, []);

  if (loading) {
    return (
      <div className="w-full max-w-4xl mt-xl">
        <h3 className="font-headline-sm text-2xl text-on-surface mb-md">Recent Activity</h3>
        <div className="bg-surface border border-outline-variant rounded-xl p-md flex justify-center text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin">refresh</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mt-xl animate-fade-in">
      <h3 className="font-headline-sm text-2xl text-on-surface mb-md">Recent Activity</h3>
      <div className="bg-surface border border-outline-variant rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-container-high border-b border-outline-variant">
            <tr>
              <th className="py-sm px-md font-label-code text-[13px] text-on-surface-variant font-medium">Status</th>
              <th className="py-sm px-md font-label-code text-[13px] text-on-surface-variant font-medium">Operation</th>
              <th className="py-sm px-md font-label-code text-[13px] text-on-surface-variant font-medium">File Name</th>
              <th className="py-sm px-md font-label-code text-[13px] text-on-surface-variant font-medium">Timestamp</th>
            </tr>
          </thead>
          <tbody className="font-body-sm text-[14px] divide-y divide-outline-variant">
            {operations.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-md text-center text-on-surface-variant italic">
                  No recent activity found.
                </td>
              </tr>
            ) : (
              operations.map((op) => (
                <tr key={op.operation_id} className="hover:bg-surface-container-low transition-colors">
                  <td className="py-sm px-md">
                    {isSuccessfulStatus(op.status) ? (
                      <span className="inline-flex items-center gap-xs text-primary bg-primary/10 px-2 py-1 rounded text-xs font-medium">
                        <CheckCircle2 size={14} /> Success
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-xs text-error bg-error-container/20 px-2 py-1 rounded text-xs font-medium">
                        <AlertCircle size={14} /> Failed
                      </span>
                    )}
                  </td>
                  <td className="py-sm px-md text-on-surface capitalize">
                    {op.operation_type} ({op.mode === 'password' ? 'Mode A' : 'Mode B'})
                  </td>
                  <td className="py-sm px-md font-label-code text-on-surface-variant">
                    {op.image_filename}
                  </td>
                  <td className="py-sm px-md text-on-surface-variant">
                    {new Date(op.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
