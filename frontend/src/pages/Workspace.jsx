import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import ChatPanel from "@/components/ChatPanel";
import PreviewPanel from "@/components/PreviewPanel";
import { CaretLeft, Lightning, Sparkle } from "@phosphor-icons/react";

export default function Workspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const templateId = params.get("template");

  const [project, setProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [code, setCode] = useState("");
  const [autoTriggered, setAutoTriggered] = useState(false);
  const templatesRef = useRef([]);

  const fetchData = async () => {
    try {
      const [pRes, mRes, tRes] = await Promise.all([
        apiClient.get(`/projects/${id}`),
        apiClient.get(`/projects/${id}/messages`),
        apiClient.get("/templates"),
      ]);
      setProject(pRes.data);
      setMessages(mRes.data);
      setCode(pRes.data.current_code || "");
      templatesRef.current = tRes.data;
    } catch (e) {
      console.error(e);
      toast.error("Failed to load project");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Auto-generate from template on first load
  useEffect(() => {
    if (
      !autoTriggered &&
      !loading &&
      templateId &&
      messages.length === 0 &&
      project &&
      templatesRef.current.length > 0
    ) {
      const tpl = templatesRef.current.find((t) => t.id === templateId);
      if (tpl) {
        setAutoTriggered(true);
        sendPrompt(tpl.prompt);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, templateId, messages, project]);

  const sendPrompt = async (prompt) => {
    if (!prompt.trim() || generating) return;
    setGenerating(true);

    // Optimistic user message
    const tempUserMsg = {
      id: "tmp_" + Date.now(),
      project_id: id,
      role: "user",
      content: prompt,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const { data } = await apiClient.post(`/projects/${id}/generate`, { prompt });
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
        return [...filtered, data.user_message, data.assistant_message];
      });
      if (data.code) {
        setCode(data.code);
        toast.success("Code generated");
      } else {
        toast.warning("No code block in response");
      }
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.detail || "Generation failed");
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setGenerating(false);
    }
  };

  const updateCodeTimer = useRef(null);
  const updateCode = (newCode) => {
    setCode(newCode);
    if (updateCodeTimer.current) clearTimeout(updateCodeTimer.current);
    updateCodeTimer.current = setTimeout(async () => {
      try {
        await apiClient.put(`/projects/${id}/code`, { code: newCode });
      } catch (e) {
        console.error(e);
      }
    }, 600);
  };

  if (loading) {
    return (
      <div className="h-screen w-full bg-[#050505] flex items-center justify-center">
        <div className="font-mono text-sm text-[#A1A1AA]">
          <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading workspace...
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-full bg-[#050505] flex flex-col overflow-hidden" data-testid="workspace-page">
      {/* Header */}
      <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-[#2A2A2A] bg-[#050505]/80 backdrop-blur-xl flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            data-testid="back-btn"
            onClick={() => navigate("/")}
            className="border border-[#2A2A2A] hover:border-[#F5F5F5] p-2 flex-shrink-0"
            title="Back"
          >
            <CaretLeft size={16} />
          </button>
          <div className="w-9 h-9 bg-[#FF3B30] flex items-center justify-center flex-shrink-0">
            <Lightning size={18} weight="fill" color="#050505" />
          </div>
          <div className="min-w-0">
            <div className="font-heading font-bold text-base tracking-tight truncate">{project?.name}</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] flex items-center gap-2">
              <span>claude sonnet 4.5</span>
              {generating && (
                <span className="text-[#FFCC00] flex items-center gap-1">
                  <Sparkle size={10} weight="fill" className="ascii-pulse" /> generating
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Workspace */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        <div className="w-full md:w-[38%] flex-shrink-0 border-r border-[#2A2A2A] flex flex-col min-h-0 max-h-[40vh] md:max-h-none">
          <ChatPanel
            messages={messages}
            onSend={sendPrompt}
            generating={generating}
          />
        </div>
        <div className="flex-1 flex flex-col min-h-0">
          <PreviewPanel code={code} onCodeChange={updateCode} />
        </div>
      </div>
    </div>
  );
}
