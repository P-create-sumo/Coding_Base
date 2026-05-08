import React, { useState } from "react";
import { LiveProvider, LivePreview, LiveError, LiveEditor } from "react-live";
import { Eye, Code, Copy, Check } from "@phosphor-icons/react";
import { toast } from "sonner";

const PRESET_SCOPE = { React };

const EMPTY_CODE = `const App = () => (
  <div className="min-h-screen bg-[#050505] text-[#F5F5F5] flex items-center justify-center p-12">
    <div className="text-center">
      <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA] mb-4">/ empty canvas</div>
      <h1 className="text-4xl font-bold tracking-tighter">Send a prompt to begin</h1>
      <p className="mt-3 text-[#A1A1AA]">Your generated UI will render here, live.</p>
    </div>
  </div>
);
render(<App />);`;

export default function PreviewPanel({ code, onCodeChange }) {
  const [tab, setTab] = useState("preview");
  const [copied, setCopied] = useState(false);

  const displayedCode = code && code.trim() ? code : EMPTY_CODE;

  const copyCode = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(displayedCode);
      } else {
        // Fallback for non-secure contexts
        const ta = document.createElement("textarea");
        ta.value = displayedCode;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      toast.success("Code copied");
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      toast.error("Copy not allowed in this context");
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#050505] min-h-0" data-testid="preview-panel">
      {/* Tabs */}
      <div className="flex items-center border-b border-[#2A2A2A] bg-[#050505] flex-shrink-0">
        <button
          data-testid="tab-preview"
          onClick={() => setTab("preview")}
          className={`px-5 py-3 font-mono text-[10px] uppercase tracking-[0.2em] flex items-center gap-2 border-r border-[#2A2A2A] ${
            tab === "preview"
              ? "bg-[#121212] text-[#FF3B30] border-b-2 border-b-[#FF3B30] -mb-px"
              : "text-[#A1A1AA] hover:text-[#F5F5F5]"
          }`}
        >
          <Eye size={12} weight="bold" /> preview
        </button>
        <button
          data-testid="tab-code"
          onClick={() => setTab("code")}
          className={`px-5 py-3 font-mono text-[10px] uppercase tracking-[0.2em] flex items-center gap-2 border-r border-[#2A2A2A] ${
            tab === "code"
              ? "bg-[#121212] text-[#FF3B30] border-b-2 border-b-[#FF3B30] -mb-px"
              : "text-[#A1A1AA] hover:text-[#F5F5F5]"
          }`}
        >
          <Code size={12} weight="bold" /> code
        </button>
        <div className="flex-1" />
        <button
          data-testid="copy-code-btn"
          onClick={copyCode}
          className="px-4 py-3 font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] hover:text-[#F5F5F5] flex items-center gap-2"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={12} weight="bold" className="text-[#34C759]" /> copied
            </>
          ) : (
            <>
              <Copy size={12} weight="bold" /> copy
            </>
          )}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden min-h-0 relative">
        <LiveProvider
          code={displayedCode}
          scope={PRESET_SCOPE}
          noInline
          enableTypeScript={false}
        >
          {tab === "preview" ? (
            <div className="h-full overflow-auto bg-white text-black" data-testid="live-preview-container">
              <LivePreview />
              <div className="border-t border-[#2A2A2A]">
                <LiveError className="live-error" />
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col bg-[#0D0D0D]" data-testid="code-editor-container">
              <div className="flex-1 overflow-auto">
                <LiveEditor
                  className="live-editor"
                  onChange={(val) => onCodeChange?.(val)}
                  style={{ minHeight: "100%" }}
                />
              </div>
              <div className="border-t border-[#2A2A2A]">
                <LiveError className="live-error" />
              </div>
            </div>
          )}
        </LiveProvider>
      </div>
    </div>
  );
}
