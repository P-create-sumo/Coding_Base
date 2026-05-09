import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import apiClient, { API } from "@/lib/api";
import { toast } from "sonner";
import ChatPanel from "@/components/ChatPanel";
import PreviewPanel from "@/components/PreviewPanel";
import VersionHistory from "@/components/VersionHistory";
import { CaretLeft, Lightning, Sparkle, ClockCounterClockwise, DownloadSimple } from "@phosphor-icons/react";

export default function Workspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const templateId = params.get("template");

  const [project, setProject] = useState(null);
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState("App.jsx");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [streamingText, setStreamingText] = useState(""); // current assistant streaming buffer
  const [autoTriggered, setAutoTriggered] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const templatesRef = useRef([]);

  const fetchData = useCallback(async () => {
    try {
      const [pRes, mRes, tRes] = await Promise.all([
        apiClient.get(`/apps/projects/${id}`),
        apiClient.get(`/apps/projects/${id}/messages`),
        apiClient.get("/apps/templates"),
      ]);
      setProject(pRes.data);
      setMessages(mRes.data);
      const projectFiles = pRes.data.files?.length
        ? pRes.data.files
        : pRes.data.current_code
          ? [{ path: "App.jsx", content: pRes.data.current_code }]
          : [];
      setFiles(projectFiles);
      templatesRef.current = tRes.data;
    } catch (e) {
      console.error(e);
      if (e.response?.status === 401) {
        navigate("/login");
        return;
      }
      toast.error("Failed to load project");
      navigate("/");
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!autoTriggered && !loading && templateId && messages.length === 0 && project && templatesRef.current.length > 0) {
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
    setStreamingText("");

    const tempUserMsg = {
      id: "tmp_" + Date.now(),
      project_id: id,
      role: "user",
      content: prompt,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await fetch(`${API}/apps/projects/${id}/generate-stream`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let realUserMsg = null;
      let finalData = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            if (evt.type === "user") {
              realUserMsg = evt.message;
              setMessages((prev) =>
                prev.map((m) => (m.id === tempUserMsg.id ? evt.message : m))
              );
            } else if (evt.type === "chunk") {
              setStreamingText((prev) => prev + evt.text);
            } else if (evt.type === "done") {
              finalData = evt;
            } else if (evt.type === "error") {
              throw new Error(evt.detail || "Stream error");
            }
          } catch (parseErr) {
            // ignore malformed
          }
        }
      }

      if (finalData) {
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
          // Ensure real user msg present
          const hasUser = realUserMsg ? filtered.some((m) => m.id === realUserMsg.id) : true;
          const base = hasUser || !realUserMsg ? filtered : [...filtered, realUserMsg];
          return [...base, finalData.assistant_message];
        });
        if (finalData.files?.length) {
          setFiles(finalData.files);
          if (!finalData.files.find((f) => f.path === activeFile)) {
            setActiveFile(finalData.files[0].path);
          }
          toast.success("Code generated");
        } else if (finalData.code) {
          setFiles([{ path: "App.jsx", content: finalData.code }]);
          toast.success("Code generated");
        } else {
          toast.warning("No code in response");
        }
      }
    } catch (e) {
      console.error(e);
      toast.error(e.message || "Generation failed");
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setGenerating(false);
      setStreamingText("");
    }
  };

  const updateCodeTimer = useRef(null);
  const updateFileContent = (path, newContent) => {
    setFiles((prev) =>
      prev.map((f) => (f.path === path ? { ...f, content: newContent } : f))
    );
    if (updateCodeTimer.current) clearTimeout(updateCodeTimer.current);
    updateCodeTimer.current = setTimeout(async () => {
      try {
        await apiClient.put(`/apps/projects/${id}/code`, { code: newContent, path });
      } catch (e) {
        console.error(e);
      }
    }, 600);
  };

  const handleRollback = async (versionId) => {
    try {
      const { data } = await apiClient.post(`/apps/projects/${id}/rollback/${versionId}`);
      setFiles(data.files || []);
      if (data.files?.length && !data.files.find((f) => f.path === activeFile)) {
        setActiveFile(data.files[0].path);
      }
      setShowVersions(false);
      toast.success("Rolled back to version");
    } catch (e) {
      toast.error("Rollback failed");
    }
  };

  const handleExport = async () => {
    try {
      const response = await fetch(`${API}/apps/projects/${id}/export`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeName = (project?.name || "project").toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 40);
      a.download = `${safeName}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Exported as .zip");
    } catch (e) {
      toast.error("Export failed");
    }
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
      <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-[#2A2A2A] bg-[#050505]/80 backdrop-blur-xl flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <button
            data-testid="back-btn"
            onClick={() => navigate("/apps")}
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
              <span>claude sonnet 4.5 · streaming</span>
              {generating && (
                <span className="text-[#FFCC00] flex items-center gap-1">
                  <Sparkle size={10} weight="fill" className="ascii-pulse" /> generating
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            data-testid="versions-btn"
            onClick={() => setShowVersions(true)}
            className="border border-[#2A2A2A] hover:border-[#FFCC00] hover:text-[#FFCC00] p-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em]"
            title="Version history"
          >
            <ClockCounterClockwise size={14} weight="bold" />
            <span className="hidden md:inline">history</span>
          </button>
          <button
            data-testid="export-btn"
            onClick={handleExport}
            className="border border-[#2A2A2A] hover:border-[#FF3B30] hover:text-[#FF3B30] p-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em]"
            title="Export as .zip"
            disabled={!files.length}
          >
            <DownloadSimple size={14} weight="bold" />
            <span className="hidden md:inline">.zip</span>
          </button>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        <div className="w-full md:w-[38%] flex-shrink-0 border-r border-[#2A2A2A] flex flex-col min-h-0 max-h-[40vh] md:max-h-none">
          <ChatPanel
            messages={messages}
            onSend={sendPrompt}
            generating={generating}
            streamingText={streamingText}
          />
        </div>
        <div className="flex-1 flex flex-col min-h-0">
          <PreviewPanel
            files={files}
            activeFile={activeFile}
            onActiveFileChange={setActiveFile}
            onCodeChange={updateFileContent}
          />
        </div>
      </div>

      {showVersions && (
        <VersionHistory
          projectId={id}
          onClose={() => setShowVersions(false)}
          onRollback={handleRollback}
        />
      )}
    </div>
  );
}
