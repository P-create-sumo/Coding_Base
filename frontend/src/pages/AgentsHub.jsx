import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import HubHeader from "@/components/HubHeader";
import { Plus, Trash, ArrowRight, Robot, Brain, Wrench, Code } from "@phosphor-icons/react";

const TYPE_META = {
  conversational: { label: "Conversational", icon: Brain, color: "#FFCC00", desc: "Persistent chat with memory" },
  autonomous: { label: "Autonomous", icon: Wrench, color: "#FF3B30", desc: "Multi-step research with tools" },
  coding: { label: "Coding", icon: Code, color: "#34C759", desc: "Iterates on a forge project" },
};

export default function AgentsHub() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", type: "conversational", description: "", kb_id: "", project_id: "" });
  const [creating, setCreating] = useState(false);

  const load = () =>
    Promise.all([
      apiClient.get("/agents"),
      apiClient.get("/knowledge"),
      apiClient.get("/apps/projects"),
    ])
      .then(([a, k, p]) => {
        setAgents(a.data);
        setKnowledgeBases(k.data);
        setProjects(p.data);
      })
      .catch(() => toast.error("Failed to load"))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const createAgent = async () => {
    if (!form.name.trim()) { toast.error("Name required"); return; }
    if (form.type === "coding" && !form.project_id) { toast.error("Coding agent needs a linked project"); return; }
    setCreating(true);
    try {
      const { data } = await apiClient.post("/agents", {
        name: form.name,
        type: form.type,
        description: form.description,
        knowledge_base_id: form.kb_id || null,
        linked_project_id: form.project_id || null,
      });
      toast.success("Agent created");
      navigate(`/agents/${data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const deleteAgent = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this agent?")) return;
    try {
      await apiClient.delete(`/agents/${id}`);
      setAgents(agents.filter((a) => a.id !== id));
      toast.success("Deleted");
    } catch { toast.error("Delete failed"); }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="agents-hub">
      <HubHeader section="Agents" sectionColor="#FFCC00">
        <button data-testid="new-agent-btn" onClick={() => setShowNew(true)} className="bg-[#FFCC00] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-2.5 flex items-center gap-2">
          <Plus size={14} weight="bold" /> New Agent
        </button>
      </HubHeader>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ overview</div>
        <h1 className="font-heading text-3xl sm:text-4xl lg:text-5xl tracking-tighter font-black leading-[0.95]">
          Three flavours of <span className="text-[#FFCC00]">agent</span>.
        </h1>
        <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
          {Object.entries(TYPE_META).map(([k, m]) => {
            const Icon = m.icon;
            return (
              <div key={k} className="bg-[#0D0D0D] border border-[#2A2A2A] p-6">
                <div className="w-12 h-12 flex items-center justify-center mb-4" style={{ background: m.color }}>
                  <Icon size={22} weight="fill" color="#050505" />
                </div>
                <div className="font-heading font-bold text-xl tracking-tight">{m.label}</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mt-1">{m.desc}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-12">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ your agents</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">Active</h2>
          </div>
        </div>

        {loading ? (
          <div className="font-mono text-sm text-[#A1A1AA]"><span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading...</div>
        ) : agents.length === 0 ? (
          <div className="border border-dashed border-[#2A2A2A] p-12 text-center">
            <Robot size={32} weight="duotone" className="mx-auto mb-4 text-[#A1A1AA]" />
            <p className="text-[#A1A1AA]">No agents yet. Spin one up to get started.</p>
            <button data-testid="empty-new-agent-btn" onClick={() => setShowNew(true)} className="mt-6 bg-[#FFCC00] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-6 py-3">
              Create your first agent
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {agents.map((a) => {
              const meta = TYPE_META[a.type];
              const Icon = meta.icon;
              return (
                <div
                  key={a.id}
                  data-testid={`agent-card-${a.id}`}
                  onClick={() => navigate(`/agents/${a.id}`)}
                  className="group cursor-pointer bg-[#121212] border border-[#2A2A2A] hover:border-[var(--accent)] p-5 flex flex-col min-h-[180px]"
                  style={{ "--accent": meta.color }}
                >
                  <div className="flex items-start justify-between">
                    <div className="w-10 h-10 flex items-center justify-center" style={{ background: meta.color }}>
                      <Icon size={18} weight="fill" color="#050505" />
                    </div>
                    <button onClick={(e) => deleteAgent(a.id, e)} className="text-[#A1A1AA] hover:text-[#FF3B30]" data-testid={`delete-agent-${a.id}`}>
                      <Trash size={14} />
                    </button>
                  </div>
                  <div className="mt-4 font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: meta.color }}>
                    {meta.label}
                  </div>
                  <h3 className="mt-1 font-heading font-bold text-xl tracking-tight line-clamp-2">{a.name}</h3>
                  {a.description && <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-2">{a.description}</p>}
                  <div className="mt-auto pt-4 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                    <span>{new Date(a.updated_at).toLocaleDateString()}</span>
                    <ArrowRight size={14} weight="bold" className="group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {showNew && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowNew(false)}>
          <div className="bg-[#121212] border border-[#2A2A2A] w-full max-w-lg p-8 slide-up max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="new-agent-modal">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ new agent</div>
            <h3 className="font-heading font-bold text-2xl tracking-tight mb-6">Configure your agent</h3>

            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Type</label>
            <div className="grid grid-cols-3 gap-2 mb-5">
              {Object.entries(TYPE_META).map(([k, m]) => {
                const Icon = m.icon;
                const selected = form.type === k;
                return (
                  <button
                    key={k}
                    data-testid={`agent-type-${k}`}
                    onClick={() => setForm({ ...form, type: k })}
                    className={`p-3 border flex flex-col items-center gap-2 ${selected ? "border-[var(--accent)] bg-[#0D0D0D]" : "border-[#2A2A2A] hover:border-[#52525B]"}`}
                    style={{ "--accent": m.color }}
                  >
                    <Icon size={20} weight={selected ? "fill" : "regular"} color={selected ? m.color : "#A1A1AA"} />
                    <span className="font-mono text-[10px] uppercase tracking-[0.15em]">{m.label}</span>
                  </button>
                );
              })}
            </div>

            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Name</label>
            <input data-testid="agent-name-input" type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Research Assistant" className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FFCC00] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5" />

            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Description (optional)</label>
            <textarea data-testid="agent-desc-input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FFCC00] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5 resize-none" />

            {form.type !== "coding" && (
              <>
                <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Knowledge base (optional, RAG)</label>
                <select data-testid="agent-kb-select" value={form.kb_id} onChange={(e) => setForm({ ...form, kb_id: e.target.value })} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FFCC00] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5">
                  <option value="">— None —</option>
                  {knowledgeBases.map((kb) => (<option key={kb.id} value={kb.id}>{kb.name} ({kb.doc_count} docs)</option>))}
                </select>
              </>
            )}

            {form.type === "coding" && (
              <>
                <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Linked project (required)</label>
                <select data-testid="agent-project-select" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FFCC00] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5">
                  <option value="">— Pick a project —</option>
                  {projects.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                </select>
              </>
            )}

            <div className="flex gap-3 mt-2">
              <button data-testid="cancel-new-agent-btn" onClick={() => setShowNew(false)} className="flex-1 bg-transparent border border-[#2A2A2A] text-[#F5F5F5] hover:border-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3">Cancel</button>
              <button data-testid="confirm-new-agent-btn" onClick={createAgent} disabled={creating} className="flex-1 bg-[#FFCC00] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50">
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
