import { useEffect, useState } from "react";
import apiClient from "@/lib/api";
import { ClockCounterClockwise, X, ArrowCounterClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function VersionHistory({ projectId, onClose, onRollback }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/apps/projects/${projectId}/versions`)
      .then(({ data }) => setVersions(data))
      .catch(() => toast.error("Failed to load versions"))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onClick={onClose}>
      <div
        className="bg-[#121212] border border-[#2A2A2A] w-full max-w-2xl max-h-[80vh] flex flex-col slide-up"
        onClick={(e) => e.stopPropagation()}
        data-testid="version-history-modal"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2A2A2A] flex-shrink-0">
          <div className="flex items-center gap-3">
            <ClockCounterClockwise size={20} weight="bold" className="text-[#FFCC00]" />
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#FFCC00]">/ version history</div>
              <div className="font-heading font-bold text-lg tracking-tight">Roll back any time</div>
            </div>
          </div>
          <button
            data-testid="close-versions-btn"
            onClick={onClose}
            className="border border-[#2A2A2A] hover:border-[#F5F5F5] p-2"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="font-mono text-sm text-[#A1A1AA]">
              <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading versions...
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-12">
              <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">/ empty</div>
              <p className="text-[#A1A1AA] text-sm">No versions yet. Generate code to start the history.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {versions.map((v, idx) => (
                <div
                  key={v.id}
                  data-testid={`version-${v.id}`}
                  className="bg-[#0D0D0D] border border-[#2A2A2A] hover:border-[#FFCC00] p-4 group"
                >
                  <div className="flex items-start gap-4">
                    <div className="font-mono text-2xl font-bold text-[#FFCC00] tabular-nums w-8 text-right flex-shrink-0">
                      {String(versions.length - idx).padStart(2, "0")}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-1">
                        {new Date(v.created_at).toLocaleString()}
                      </div>
                      <div className="text-sm text-[#F5F5F5] line-clamp-2 mb-2">{v.prompt || "(no prompt)"}</div>
                      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                        {v.files?.length || 0} file{v.files?.length === 1 ? "" : "s"}
                      </div>
                    </div>
                    <button
                      data-testid={`rollback-${v.id}`}
                      onClick={() => onRollback(v.id)}
                      className="bg-transparent border border-[#2A2A2A] text-[#F5F5F5] hover:border-[#FFCC00] hover:text-[#FFCC00] font-bold uppercase text-[10px] tracking-wide px-3 py-2 flex items-center gap-2 flex-shrink-0"
                    >
                      <ArrowCounterClockwise size={12} weight="bold" /> Rollback
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
