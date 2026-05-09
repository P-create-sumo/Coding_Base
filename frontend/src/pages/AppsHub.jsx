import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import HubHeader from "@/components/HubHeader";
import { Plus, Trash, ArrowRight, Sparkle, Code } from "@phosphor-icons/react";

export default function AppsHub() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newKbId, setNewKbId] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    Promise.all([
      apiClient.get("/apps/projects"),
      apiClient.get("/apps/templates"),
      apiClient.get("/knowledge"),
    ])
      .then(([p, t, k]) => {
        setProjects(p.data);
        setTemplates(t.data);
        setKnowledgeBases(k.data);
      })
      .catch(() => toast.error("Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const createProject = async (templateId = null, prefilledName = "") => {
    if (creating) return;
    const name = prefilledName || newName.trim() || "Untitled Project";
    setCreating(true);
    try {
      const { data } = await apiClient.post("/apps/projects", {
        name,
        description: newDesc,
        template_id: templateId,
        knowledge_base_id: newKbId || null,
      });
      toast.success("Project created");
      navigate(`/apps/${data.id}${templateId ? `?template=${templateId}` : ""}`);
    } catch {
      toast.error("Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this project permanently?")) return;
    try {
      await apiClient.delete(`/apps/projects/${id}`);
      setProjects(projects.filter((p) => p.id !== id));
      toast.success("Deleted");
    } catch {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="apps-hub">
      <HubHeader section="App Creator" sectionColor="#FF3B30">
        <button
          data-testid="new-project-header-btn"
          onClick={() => setShowNew(true)}
          className="bg-[#F5F5F5] text-[#050505] hover:bg-[#FF3B30] hover:text-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-2.5 flex items-center gap-2"
        >
          <Plus size={14} weight="bold" /> New
        </button>
      </HubHeader>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12 border-b border-[#2A2A2A]">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ 01</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Templates</h2>
            <p className="mt-3 text-[#A1A1AA] max-w-lg">Pre-built starting points. Pick one to bootstrap.</p>
          </div>
          <Sparkle size={32} weight="duotone" className="hidden md:block text-[#FFCC00]" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              data-testid={`template-card-${tpl.id}`}
              onClick={() => createProject(tpl.id, tpl.name)}
              className="group cursor-pointer bg-[#121212] border border-[#2A2A2A] hover:border-[#FF3B30] flex flex-col"
            >
              <div className="aspect-video overflow-hidden border-b border-[#2A2A2A] bg-[#0D0D0D] relative">
                <img src={tpl.thumbnail} alt={tpl.name} className="w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300" />
                <div className="absolute top-3 left-3 bg-[#050505] border border-[#2A2A2A] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em]">
                  {tpl.category}
                </div>
              </div>
              <div className="p-5 flex-1 flex flex-col">
                <h3 className="font-heading font-bold text-lg tracking-tight">{tpl.name}</h3>
                <p className="text-sm text-[#A1A1AA] mt-2 leading-relaxed flex-1">{tpl.description}</p>
                <div className="mt-5 pt-4 border-t border-[#2A2A2A] flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">use template</span>
                  <ArrowRight size={16} weight="bold" className="text-[#A1A1AA] group-hover:text-[#FF3B30] group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ 02</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Your projects</h2>
            <p className="mt-3 text-[#A1A1AA]">{loading ? "Loading..." : `${projects.length} project${projects.length === 1 ? "" : "s"}`}</p>
          </div>
        </div>

        {!loading && projects.length === 0 ? (
          <div className="border border-dashed border-[#2A2A2A] p-12 text-center">
            <Code size={32} weight="duotone" className="mx-auto mb-4 text-[#A1A1AA]" />
            <p className="text-[#A1A1AA]">No projects yet. Pick a template or start fresh.</p>
            <button
              data-testid="empty-new-project-btn"
              onClick={() => setShowNew(true)}
              className="mt-6 bg-[#F5F5F5] text-[#050505] hover:bg-[#FF3B30] hover:text-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-6 py-3"
            >
              Create your first project
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {projects.map((p) => (
              <div
                key={p.id}
                data-testid={`project-card-${p.id}`}
                onClick={() => navigate(`/apps/${p.id}`)}
                className="group cursor-pointer bg-[#121212] border border-[#2A2A2A] hover:border-[#FF3B30] p-5 flex flex-col min-h-[160px]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">{new Date(p.updated_at).toLocaleDateString()}</div>
                  <button data-testid={`delete-project-${p.id}`} onClick={(e) => deleteProject(p.id, e)} className="text-[#A1A1AA] hover:text-[#FF3B30]" title="Delete">
                    <Trash size={14} />
                  </button>
                </div>
                <h3 className="mt-3 font-heading font-bold text-xl tracking-tight line-clamp-2">{p.name}</h3>
                {p.description && <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-2">{p.description}</p>}
                <div className="mt-auto pt-4 flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                    {p.current_code ? "● ready" : "○ empty"}
                    {p.knowledge_base_id ? " · 📚" : ""}
                  </span>
                  <ArrowRight size={14} weight="bold" className="text-[#A1A1AA] group-hover:text-[#FF3B30] group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {showNew && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowNew(false)}>
          <div className="bg-[#121212] border border-[#2A2A2A] w-full max-w-md p-8 slide-up" onClick={(e) => e.stopPropagation()} data-testid="new-project-modal">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-3">/ new project</div>
            <h3 className="font-heading font-bold text-2xl tracking-tight mb-6">Name your project</h3>
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Project name</label>
            <input data-testid="new-project-name-input" type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="My awesome dashboard" className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5" autoFocus />
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Description (optional)</label>
            <textarea data-testid="new-project-desc-input" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="Brief description..." rows={2} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5 resize-none" />
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Knowledge base (optional, RAG)</label>
            <select data-testid="new-project-kb-select" value={newKbId} onChange={(e) => setNewKbId(e.target.value)} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-6">
              <option value="">— None —</option>
              {knowledgeBases.map((kb) => (
                <option key={kb.id} value={kb.id}>{kb.name} ({kb.doc_count} docs)</option>
              ))}
            </select>
            <div className="flex gap-3">
              <button data-testid="cancel-new-project-btn" onClick={() => setShowNew(false)} className="flex-1 bg-transparent border border-[#2A2A2A] text-[#F5F5F5] hover:border-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3">Cancel</button>
              <button data-testid="confirm-new-project-btn" onClick={() => createProject(null)} disabled={creating} className="flex-1 bg-[#FF3B30] text-[#F5F5F5] hover:bg-[#F5F5F5] hover:text-[#050505] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50">
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
