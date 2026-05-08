import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import { Lightning, Plus, Sparkle, Trash, ArrowRight, GithubLogo } from "@phosphor-icons/react";

export default function LandingPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  useEffect(() => {
    Promise.all([
      apiClient.get("/projects"),
      apiClient.get("/templates"),
    ])
      .then(([p, t]) => {
        setProjects(p.data);
        setTemplates(t.data);
      })
      .catch((e) => {
        console.error(e);
        toast.error("Failed to load data");
      })
      .finally(() => setLoading(false));
  }, []);

  const createProject = async (templateId = null, prefilledName = "") => {
    if (creating) return;
    const name = prefilledName || newName.trim() || "Untitled Project";
    setCreating(true);
    try {
      const { data } = await apiClient.post("/projects", {
        name,
        description: newDesc,
        template_id: templateId,
      });
      toast.success("Project created");
      navigate(`/project/${data.id}${templateId ? `?template=${templateId}` : ""}`);
    } catch (e) {
      console.error(e);
      toast.error("Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this project permanently?")) return;
    try {
      await apiClient.delete(`/projects/${id}`);
      setProjects(projects.filter((p) => p.id !== id));
      toast.success("Deleted");
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="landing-page">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#2A2A2A]">
        <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#FF3B30] flex items-center justify-center">
              <Lightning size={20} weight="fill" color="#050505" />
            </div>
            <div>
              <div className="font-heading font-black text-lg tracking-tighter leading-none">FORGE</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] leading-none mt-0.5">/ ai app builder</div>
            </div>
          </div>
          <button
            data-testid="new-project-header-btn"
            onClick={() => setShowNew(true)}
            className="bg-[#F5F5F5] text-[#050505] hover:bg-[#FF3B30] hover:text-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-2.5 flex items-center gap-2"
          >
            <Plus size={14} weight="bold" /> New Project
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 pt-20 pb-16 border-b border-[#2A2A2A]">
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 md:col-span-8">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-6 flex items-center gap-2">
              <span className="w-2 h-2 bg-[#FF3B30] rounded-full ascii-pulse" />
              <span>v1.0 / now in beta</span>
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black leading-[0.95]">
              Describe an app.<br />
              <span className="text-[#FF3B30]">Ship it</span> in seconds.
            </h1>
            <p className="mt-6 text-base md:text-lg text-[#A1A1AA] max-w-xl leading-relaxed">
              FORGE is a no-code AI workshop. Describe your interface in plain English,
              powered by Claude Sonnet 4.5, and watch it materialise live.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <button
                data-testid="hero-start-btn"
                onClick={() => setShowNew(true)}
                className="bg-[#FF3B30] text-[#F5F5F5] hover:bg-[#F5F5F5] hover:text-[#050505] font-bold uppercase text-sm tracking-wide px-7 py-4 flex items-center gap-3"
              >
                Start Building <ArrowRight size={16} weight="bold" />
              </button>
              <a
                href="#templates"
                className="text-[#F5F5F5] border border-[#2A2A2A] hover:border-[#F5F5F5] font-bold uppercase text-sm tracking-wide px-7 py-4"
              >
                Browse Templates
              </a>
            </div>
          </div>
          <div className="hidden md:block col-span-4 border-l border-[#2A2A2A] pl-8">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA] mb-4">/ engine</div>
            <div className="space-y-4">
              <Stat label="Model" value="Claude Sonnet 4.5" />
              <Stat label="Latency" value="< 8s" />
              <Stat label="Templates" value={templates.length} />
              <Stat label="Projects" value={projects.length} />
            </div>
          </div>
        </div>
      </section>

      {/* Templates */}
      <section id="templates" className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-16 border-b border-[#2A2A2A]">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ 01</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">
              Start from a template
            </h2>
            <p className="mt-3 text-[#A1A1AA] max-w-lg">
              Pre-built starting points for common SaaS interfaces. Pick one, customise via chat.
            </p>
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
                <img
                  src={tpl.thumbnail}
                  alt={tpl.name}
                  className="w-full h-full object-cover opacity-70 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
                />
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

      {/* Recent Projects */}
      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-16">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ 02</div>
            <h2 className="font-heading text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold">
              Your projects
            </h2>
            <p className="mt-3 text-[#A1A1AA]">
              {loading ? "Loading..." : `${projects.length} project${projects.length === 1 ? "" : "s"}`}
            </p>
          </div>
        </div>

        {loading ? (
          <AsciiLoader />
        ) : projects.length === 0 ? (
          <div className="border border-dashed border-[#2A2A2A] p-12 text-center">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA] mb-3">/ empty</div>
            <p className="text-[#A1A1AA]">No projects yet. Pick a template above or start fresh.</p>
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
                onClick={() => navigate(`/project/${p.id}`)}
                className="group cursor-pointer bg-[#121212] border border-[#2A2A2A] hover:border-[#FF3B30] p-5 flex flex-col min-h-[160px]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                    {new Date(p.updated_at).toLocaleDateString()}
                  </div>
                  <button
                    data-testid={`delete-project-${p.id}`}
                    onClick={(e) => deleteProject(p.id, e)}
                    className="text-[#A1A1AA] hover:text-[#FF3B30]"
                    title="Delete"
                  >
                    <Trash size={14} />
                  </button>
                </div>
                <h3 className="mt-3 font-heading font-bold text-xl tracking-tight line-clamp-2">{p.name}</h3>
                {p.description && (
                  <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-2">{p.description}</p>
                )}
                <div className="mt-auto pt-4 flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                    {p.current_code ? "● ready" : "○ empty"}
                  </span>
                  <ArrowRight size={14} weight="bold" className="text-[#A1A1AA] group-hover:text-[#FF3B30] group-hover:translate-x-1 transition-all" />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t border-[#2A2A2A] py-8">
        <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA]">
            © {new Date().getFullYear()} FORGE / built with claude sonnet 4.5
          </div>
          <a href="https://github.com" target="_blank" rel="noreferrer" className="text-[#A1A1AA] hover:text-[#F5F5F5] flex items-center gap-2 text-xs uppercase tracking-[0.2em] font-mono">
            <GithubLogo size={16} /> source
          </a>
        </div>
      </footer>

      {/* New Project Modal */}
      {showNew && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowNew(false)}>
          <div
            className="bg-[#121212] border border-[#2A2A2A] w-full max-w-md p-8 slide-up"
            onClick={(e) => e.stopPropagation()}
            data-testid="new-project-modal"
          >
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-3">/ new project</div>
            <h3 className="font-heading font-bold text-2xl tracking-tight mb-6">Name your project</h3>
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Project name</label>
            <input
              data-testid="new-project-name-input"
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="My awesome dashboard"
              className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-5"
              autoFocus
            />
            <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mb-2">Description (optional)</label>
            <textarea
              data-testid="new-project-desc-input"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Brief description..."
              rows={3}
              className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-6 resize-none"
            />
            <div className="flex gap-3">
              <button
                data-testid="cancel-new-project-btn"
                onClick={() => setShowNew(false)}
                className="flex-1 bg-transparent border border-[#2A2A2A] text-[#F5F5F5] hover:border-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3"
              >
                Cancel
              </button>
              <button
                data-testid="confirm-new-project-btn"
                onClick={() => createProject(null)}
                disabled={creating}
                className="flex-1 bg-[#FF3B30] text-[#F5F5F5] hover:bg-[#F5F5F5] hover:text-[#050505] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="border-b border-[#2A2A2A] pb-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">{label}</div>
      <div className="font-heading text-2xl font-bold tracking-tight mt-1">{value}</div>
    </div>
  );
}

function AsciiLoader() {
  return (
    <div className="font-mono text-sm text-[#A1A1AA] flex items-center gap-3">
      <span className="ascii-pulse">▓▓▓▓▓░░░░░</span>
      <span>loading projects...</span>
    </div>
  );
}
