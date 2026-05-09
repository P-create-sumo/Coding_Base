import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import HubHeader from "@/components/HubHeader";
import { Plus, Trash, ArrowRight, BookOpen } from "@phosphor-icons/react";

export default function KnowledgeHub() {
  const navigate = useNavigate();
  const [kbs, setKbs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    apiClient.get("/knowledge")
      .then(({ data }) => setKbs(data))
      .catch(() => toast.error("Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const create = async () => {
    if (!name.trim()) { toast.error("Name required"); return; }
    setCreating(true);
    try {
      const { data } = await apiClient.post("/knowledge", { name, description: desc });
      toast.success("Knowledge base created");
      navigate(`/knowledge/${data.id}`);
    } catch { toast.error("Create failed"); }
    finally { setCreating(false); }
  };

  const del = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this knowledge base and all its documents?")) return;
    try {
      await apiClient.delete(`/knowledge/${id}`);
      setKbs(kbs.filter((k) => k.id !== id));
      toast.success("Deleted");
    } catch { toast.error("Delete failed"); }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="knowledge-hub">
      <HubHeader section="Knowledge" sectionColor="#34C759">
        <button data-testid="new-kb-btn" onClick={() => setShowNew(true)} className="bg-[#34C759] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-2.5 flex items-center gap-2">
          <Plus size={14} weight="bold" /> New KB
        </button>
      </HubHeader>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#34C759] mb-3">/ rag knowledge bases</div>
        <h1 className="font-heading text-3xl sm:text-4xl lg:text-5xl tracking-tighter font-black leading-[0.95]">
          Ground your AI<br /> in <span className="text-[#34C759]">your data</span>.
        </h1>
        <p className="mt-6 text-base text-[#A1A1AA] max-w-xl">
          Upload PDF, DOCX, TXT or scrape URLs. Embedded into vector search, available as context to apps & agents.
        </p>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12">
        {loading ? (
          <div className="font-mono text-sm text-[#A1A1AA]"><span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading...</div>
        ) : kbs.length === 0 ? (
          <div className="border border-dashed border-[#2A2A2A] p-12 text-center">
            <BookOpen size={32} weight="duotone" className="mx-auto mb-4 text-[#A1A1AA]" />
            <p className="text-[#A1A1AA]">No knowledge bases yet. Create one to start uploading documents.</p>
            <button data-testid="empty-new-kb-btn" onClick={() => setShowNew(true)} className="mt-6 bg-[#34C759] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-6 py-3">
              Create your first KB
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {kbs.map((kb) => (
              <div
                key={kb.id}
                data-testid={`kb-card-${kb.id}`}
                onClick={() => navigate(`/knowledge/${kb.id}`)}
                className="group cursor-pointer bg-[#121212] border border-[#2A2A2A] hover:border-[#34C759] p-5 flex flex-col min-h-[180px]"
              >
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 bg-[#34C759] flex items-center justify-center">
                    <BookOpen size={18} weight="fill" color="#050505" />
                  </div>
                  <button onClick={(e) => del(kb.id, e)} className="text-[#A1A1AA] hover:text-[#FF3B30]" data-testid={`delete-kb-${kb.id}`}>
                    <Trash size={14} />
                  </button>
                </div>
                <h3 className="mt-4 font-heading font-bold text-xl tracking-tight line-clamp-2">{kb.name}</h3>
                {kb.description && <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-2">{kb.description}</p>}
                <div className="mt-auto pt-4 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                  <span>{kb.doc_count || 0} docs · {kb.chunk_count || 0} chunks</span>
                  <ArrowRight size={14} weight="bold" className="group-hover:translate-x-1 transition-transform group-hover:text-[#34C759]" />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {showNew && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowNew(false)}>
          <div className="bg-[#121212] border border-[#2A2A2A] w-full max-w-md p-8 slide-up" onClick={(e) => e.stopPropagation()} data-testid="new-kb-modal">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#34C759] mb-3">/ new knowledge base</div>
            <h3 className="font-heading font-bold text-2xl tracking-tight mb-6">Name your KB</h3>
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Name</label>
            <input data-testid="new-kb-name-input" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Product Docs" className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#34C759] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5" autoFocus />
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Description</label>
            <textarea data-testid="new-kb-desc-input" value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#34C759] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-6 resize-none" />
            <div className="flex gap-3">
              <button data-testid="cancel-new-kb-btn" onClick={() => setShowNew(false)} className="flex-1 bg-transparent border border-[#2A2A2A] text-[#F5F5F5] hover:border-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3">Cancel</button>
              <button data-testid="confirm-new-kb-btn" onClick={create} disabled={creating} className="flex-1 bg-[#34C759] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50">
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
