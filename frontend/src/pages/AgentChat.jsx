import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient, { API } from "@/lib/api";
import { toast } from "sonner";
import HubHeader from "@/components/HubHeader";
import { PaperPlaneTilt, User, Sparkle, Wrench, Brain, Code, MagnifyingGlass, Globe, Calculator, BookOpen } from "@phosphor-icons/react";

const TYPE_META = {
  conversational: { color: "#FFCC00", icon: Brain, label: "Conversational" },
  autonomous: { color: "#FF3B30", icon: Wrench, label: "Autonomous" },
  coding: { color: "#34C759", icon: Code, label: "Coding" },
};

const TOOL_ICONS = {
  web_search: MagnifyingGlass,
  read_url: Globe,
  calculator: Calculator,
  knowledge_query: BookOpen,
};

export default function AgentChat() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState([]); // for autonomous agents during a run
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef(null);

  useEffect(() => {
    Promise.all([apiClient.get(`/agents/${id}`), apiClient.get(`/agents/${id}/messages`)])
      .then(([a, m]) => { setAgent(a.data); setMessages(m.data); })
      .catch(() => { toast.error("Failed to load agent"); navigate("/agents"); })
      .finally(() => setLoading(false));
  }, [id, navigate]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, steps, running]);

  const sendConversational = async (prompt) => {
    setRunning(true);
    const tmp = { id: "tmp_" + Date.now(), agent_id: id, role: "user", content: prompt, created_at: new Date().toISOString() };
    setMessages((p) => [...p, tmp]);
    try {
      const { data } = await apiClient.post(`/agents/${id}/chat`, { prompt });
      const refresh = await apiClient.get(`/agents/${id}/messages`);
      setMessages(refresh.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Chat failed");
      setMessages((p) => p.filter((m) => m.id !== tmp.id));
    } finally {
      setRunning(false);
    }
  };

  const sendAutonomous = async (prompt) => {
    setRunning(true);
    setSteps([]);
    const tmp = { id: "tmp_" + Date.now(), agent_id: id, role: "user", content: prompt, created_at: new Date().toISOString() };
    setMessages((p) => [...p, tmp]);
    try {
      const response = await fetch(`${API}/agents/${id}/run-task`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          if (!part.trim().startsWith("data:")) continue;
          try {
            const evt = JSON.parse(part.slice(part.indexOf("data:") + 5).trim());
            if (evt.type === "user") {
              setMessages((p) => p.map((m) => (m.id === tmp.id ? evt.message : m)));
            } else if (evt.type === "step") {
              setSteps((p) => [...p, { kind: "thought", text: evt.thought, step: evt.step }]);
            } else if (evt.type === "tool_call") {
              setSteps((p) => [...p, { kind: "tool_call", tool: evt.tool, args: evt.args, step: evt.step }]);
            } else if (evt.type === "tool_result") {
              setSteps((p) => [...p, { kind: "tool_result", tool: evt.tool, result: evt.result, step: evt.step }]);
            } else if (evt.type === "final") {
              setMessages((p) => [...p, evt.message]);
              setSteps([]);
            } else if (evt.type === "error") {
              throw new Error(evt.detail);
            }
          } catch {}
        }
      }
    } catch (e) {
      toast.error(e.message || "Task failed");
      setMessages((p) => p.filter((m) => m.id !== tmp.id));
      setSteps([]);
    } finally {
      setRunning(false);
    }
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    const prompt = input.trim();
    if (!prompt || running) return;
    setInput("");
    if (agent.type === "autonomous") await sendAutonomous(prompt);
    else await sendConversational(prompt);
  };

  if (loading || !agent) {
    return (
      <div className="h-screen w-full bg-[#050505] flex items-center justify-center">
        <div className="font-mono text-sm text-[#A1A1AA]"><span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading agent...</div>
      </div>
    );
  }

  const meta = TYPE_META[agent.type];
  const TypeIcon = meta.icon;
  const visibleMessages = messages.filter((m) => m.role === "user" || m.role === "assistant");

  return (
    <div className="h-screen w-full bg-[#050505] flex flex-col overflow-hidden" data-testid="agent-chat">
      <HubHeader section={`Agent / ${agent.name}`} sectionColor={meta.color} />

      <div className="border-b border-[#2A2A2A] bg-[#0D0D0D] flex-shrink-0">
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center gap-3">
          <div className="w-8 h-8 flex items-center justify-center" style={{ background: meta.color }}>
            <TypeIcon size={16} weight="fill" color="#050505" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-heading font-bold text-base truncate">{agent.name}</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] truncate">
              {meta.label}
              {agent.knowledge_base_id && " · 📚 kb attached"}
              {agent.linked_project_id && " · 🔗 project linked"}
            </div>
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto" data-testid="agent-messages">
        <div className="max-w-4xl mx-auto px-6 py-6 space-y-5">
          {visibleMessages.length === 0 && !running && (
            <div className="text-center py-12">
              <Sparkle size={36} weight="duotone" className="text-[#FFCC00] mx-auto mb-4" />
              <h3 className="font-heading font-bold text-2xl tracking-tight">{agent.name}</h3>
              <p className="text-sm text-[#A1A1AA] mt-3 max-w-md mx-auto leading-relaxed">
                {agent.type === "autonomous"
                  ? "Give me a research task. I'll search the web, read pages, calculate, or query the knowledge base."
                  : agent.type === "coding"
                  ? "Tell me what to change in the linked project. I'll output the updated App.jsx."
                  : "Start a conversation. I'll remember the context as we chat."}
              </p>
            </div>
          )}

          {visibleMessages.map((m) => (
            <MessageRow key={m.id} msg={m} accent={meta.color} />
          ))}

          {running && agent.type === "autonomous" && (
            <StepStream steps={steps} accent={meta.color} />
          )}

          {running && agent.type !== "autonomous" && (
            <div className="flex gap-3 slide-up" data-testid="agent-thinking">
              <div className="w-7 h-7 flex items-center justify-center flex-shrink-0" style={{ background: meta.color }}>
                <Sparkle size={14} weight="fill" color="#050505" />
              </div>
              <div className="font-mono text-sm text-[#A1A1AA] pt-1.5">
                <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> thinking<span className="cursor-blink ml-1">█</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleSend} className="border-t border-[#2A2A2A] bg-[#050505] flex-shrink-0">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="border border-[#2A2A2A] focus-within:border-[var(--accent)] bg-[#0D0D0D] flex items-end gap-2 p-2" style={{ "--accent": meta.color }}>
            <textarea
              data-testid="agent-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) handleSend(e); }}
              disabled={running}
              placeholder={agent.type === "autonomous" ? "Give me a task to research..." : agent.type === "coding" ? "What to change in the project?" : "Type a message..."}
              rows={2}
              className="flex-1 bg-transparent text-[#F5F5F5] placeholder-[#52525B] focus:outline-none resize-none px-2 py-1 text-sm font-mono disabled:opacity-50"
            />
            <button
              data-testid="agent-send-btn"
              type="submit"
              disabled={running || !input.trim()}
              className="text-[#050505] hover:bg-[#F5F5F5] disabled:opacity-30 p-2.5 flex-shrink-0"
              style={{ background: meta.color }}
            >
              <PaperPlaneTilt size={16} weight="bold" />
            </button>
          </div>
          <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[#52525B]">
            enter to send · shift+enter newline · {meta.label} agent
          </div>
        </div>
      </form>
    </div>
  );
}

function MessageRow({ msg, accent }) {
  const isUser = msg.role === "user";
  const content = msg.content || "";
  return (
    <div className="flex gap-3 slide-up" data-testid={`agent-msg-${msg.id}`}>
      <div className={`w-7 h-7 flex items-center justify-center flex-shrink-0 ${isUser ? "bg-[#F5F5F5]" : ""}`} style={!isUser ? { background: accent } : {}}>
        {isUser ? <User size={14} weight="bold" color="#050505" /> : <Sparkle size={14} weight="fill" color="#050505" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] mb-2" style={{ color: isUser ? "#A1A1AA" : accent }}>
          / {isUser ? "user" : "assistant"}
        </div>
        <div className="text-sm text-[#F5F5F5] whitespace-pre-wrap break-words leading-relaxed">{content}</div>
      </div>
    </div>
  );
}

function StepStream({ steps, accent }) {
  return (
    <div className="flex gap-3 slide-up" data-testid="agent-steps">
      <div className="w-7 h-7 flex items-center justify-center flex-shrink-0" style={{ background: accent }}>
        <Sparkle size={14} weight="fill" color="#050505" className="ascii-pulse" />
      </div>
      <div className="flex-1 min-w-0 space-y-3">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: accent }}>/ working...</div>
        {steps.map((s, i) => {
          if (s.kind === "thought" && s.text) {
            return (
              <div key={i} className="text-sm text-[#A1A1AA] italic border-l-2 border-[#2A2A2A] pl-3">
                {s.text}
              </div>
            );
          }
          if (s.kind === "tool_call") {
            const Icon = TOOL_ICONS[s.tool] || Wrench;
            return (
              <div key={i} className="border border-[#2A2A2A] bg-[#0D0D0D] p-3">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: accent }}>
                  <Icon size={12} weight="bold" /> calling {s.tool}
                </div>
                <pre className="mt-2 text-xs text-[#A1A1AA] whitespace-pre-wrap break-words">{JSON.stringify(s.args, null, 2)}</pre>
              </div>
            );
          }
          if (s.kind === "tool_result") {
            const Icon = TOOL_ICONS[s.tool] || Wrench;
            return (
              <div key={i} className="border border-[#2A2A2A] bg-[#050505] p-3">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[#34C759]">
                  <Icon size={12} weight="bold" /> {s.tool} result
                </div>
                <pre className="mt-2 text-xs text-[#A1A1AA] whitespace-pre-wrap break-words max-h-40 overflow-y-auto">{s.result}</pre>
              </div>
            );
          }
          return null;
        })}
        <div className="font-mono text-xs text-[#A1A1AA]"><span className="ascii-pulse">▓▓▓▓▓░░░░░</span><span className="cursor-blink ml-1">█</span></div>
      </div>
    </div>
  );
}
