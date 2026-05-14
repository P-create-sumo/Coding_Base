import { Link, useNavigate } from "react-router-dom";
import { Lightning, Code, Robot, BookOpen, ArrowRight } from "@phosphor-icons/react";
import { useState, useEffect } from "react";
import apiClient from "@/lib/api";

const FEATURES = [
  {
    id: "apps",
    title: "App Creator",
    code: "/ 01",
    href: "/apps",
    icon: Code,
    accent: "#FF3B30",
    tagline: "Describe → ship a React app",
    description:
      "Generate complete, runnable React projects from plain English. Live preview, file editor, version history, .zip export.",
    bullets: ["Claude Sonnet 4.5", "Multi-file output", "Vite-ready exports"],
  },
  {
    id: "agents",
    title: "Agents",
    code: "/ 02",
    href: "/agents",
    icon: Robot,
    accent: "#FFCC00",
    tagline: "Autonomous · Conversational · Coding",
    description:
      "Spin up AI agents that research with web search, hold ongoing conversations, or iterate on your projects autonomously.",
    bullets: ["Web search + URL read", "Persistent memory", "Coding loops"],
  },
  {
    id: "knowledge",
    title: "Knowledge",
    code: "/ 03",
    href: "/knowledge",
    icon: BookOpen,
    accent: "#34C759",
    tagline: "RAG over your documents",
    description:
      "Upload PDF / DOCX / TXT or scrape URLs. Embedded in MongoDB. Plug knowledge bases into agents and apps for grounded answers.",
    bullets: ["PDF · DOCX · TXT · URL", "Vector search", "Shared with agents + apps"],
  },
];

export default function HubHome() {
  const navigate = useNavigate();
  const [counts, setCounts] = useState({ apps: 0, agents: 0, knowledge: 0 });

  useEffect(() => {
    Promise.all([
      apiClient.get("/apps/projects"),
      apiClient.get("/agents"),
      apiClient.get("/knowledge"),
    ])
      .then(([a, ag, k]) =>
        setCounts({ apps: a.data.length, agents: ag.data.length, knowledge: k.data.length })
      )
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="hub-home">
      <header className="sticky top-0 z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#2A2A2A]">
        <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#FF3B30] flex items-center justify-center">
              <Lightning size={20} weight="fill" color="#050505" />
            </div>
            <div>
              <div className="font-heading font-black text-lg tracking-tighter leading-none">FORGE</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] leading-none mt-0.5">/ ai platform</div>
            </div>
          </Link>

        </div>
      </header>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 pt-20 pb-16 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-6 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#FF3B30] rounded-full ascii-pulse" />
          <span>v2.0 / three-in-one ai workshop</span>
        </div>
        <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black leading-[0.95] max-w-4xl">
          Welcome back, <span className="text-[#FF3B30]">{user?.name?.split(" ")[0] || "builder"}</span>.<br />
          Pick your tool.
        </h1>
        <p className="mt-6 text-base md:text-lg text-[#A1A1AA] max-w-2xl leading-relaxed">
          Three workspaces, one platform. Build apps, deploy agents, ground them in your docs.
        </p>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            const count = counts[f.id];
            return (
              <button
                key={f.id}
                data-testid={`hub-card-${f.id}`}
                onClick={() => navigate(f.href)}
                className="group relative text-left bg-[#121212] border border-[#2A2A2A] hover:border-[var(--accent)] p-8 flex flex-col min-h-[420px] overflow-hidden"
                style={{ "--accent": f.accent }}
              >
                <div className="flex items-center justify-between mb-12">
                  <div
                    className="w-14 h-14 flex items-center justify-center"
                    style={{ background: f.accent }}
                  >
                    <Icon size={26} weight="fill" color="#050505" />
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: f.accent }}>
                    {f.code}
                  </div>
                </div>
                <h2 className="font-heading text-3xl md:text-4xl font-black tracking-tighter leading-none">
                  {f.title}
                </h2>
                <div className="mt-3 font-mono text-xs uppercase tracking-[0.15em] text-[#A1A1AA]">
                  {f.tagline}
                </div>
                <p className="mt-6 text-sm text-[#A1A1AA] leading-relaxed flex-1">{f.description}</p>
                <div className="mt-6 space-y-1.5">
                  {f.bullets.map((b) => (
                    <div key={b} className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#52525B]">
                      → {b}
                    </div>
                  ))}
                </div>
                <div className="mt-8 pt-6 border-t border-[#2A2A2A] flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
                    {count} item{count === 1 ? "" : "s"}
                  </span>
                  <span
                    className="font-bold text-xs uppercase tracking-wide flex items-center gap-2 group-hover:translate-x-1 transition-transform"
                    style={{ color: f.accent }}
                  >
                    Enter <ArrowRight size={14} weight="bold" />
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <footer className="border-t border-[#2A2A2A] py-8">
        <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA]">
          © {new Date().getFullYear()} FORGE / built with claude sonnet 4.5
        </div>
      </footer>
    </div>
  );
}

function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const initial = user.name?.[0]?.toUpperCase() || "U";
  return (
    <div className="relative">
      <button
        data-testid="user-menu-btn"
        onClick={() => setOpen(!open)}
        className="w-9 h-9 bg-[#121212] border border-[#2A2A2A] hover:border-[#FF3B30] flex items-center justify-center overflow-hidden"
        title={user.name}
      >
        {user.picture ? (
          <img src={user.picture} alt={user.name} className="w-full h-full object-cover" />
        ) : (
          <span className="font-bold">{initial}</span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-64 bg-[#121212] border border-[#2A2A2A] z-50 slide-up">
            <div className="p-4 border-b border-[#2A2A2A]">
              <div className="font-bold text-sm truncate">{user.name}</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] truncate mt-1">{user.email}</div>
            </div>
            <button
              data-testid="logout-btn"
              onClick={onLogout}
              className="w-full px-4 py-3 text-left text-sm hover:bg-[#1A1A1A] hover:text-[#FF3B30] flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em]"
            >
              <SignOut size={12} weight="bold" /> log out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
