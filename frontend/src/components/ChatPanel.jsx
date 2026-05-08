import { useEffect, useRef, useState } from "react";
import { PaperPlaneTilt, User, Sparkle, Code } from "@phosphor-icons/react";

export default function ChatPanel({ messages, onSend, generating, streamingText }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, generating, streamingText]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || generating) return;
    onSend(input);
    setInput("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Strip code/file blocks from streaming preview for clarity
  const cleanStreamingText = streamingText
    ?.replace(/===FILE:[\s\S]*?===END===/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .trim();

  return (
    <div className="h-full flex flex-col bg-[#050505] min-h-0" data-testid="chat-panel">
      <div className="px-5 py-3 border-b border-[#2A2A2A] flex items-center justify-between flex-shrink-0">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">/ chat</div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">
          {messages.length} {messages.length === 1 ? "msg" : "msgs"}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-5 min-h-0" data-testid="chat-messages">
        {messages.length === 0 && !generating && (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <Sparkle size={36} weight="duotone" className="text-[#FFCC00] mb-4" />
            <h3 className="font-heading font-bold text-xl tracking-tight">Describe your app</h3>
            <p className="text-sm text-[#A1A1AA] mt-2 max-w-xs leading-relaxed">
              Be specific about layout, content, and styling. The AI will generate it live on the right.
            </p>
            <div className="mt-6 space-y-2 w-full max-w-xs">
              {[
                "A pricing page with 3 tiers",
                "A dashboard with KPI cards",
                "A todo list with categories",
              ].map((s) => (
                <button
                  key={s}
                  data-testid={`suggestion-${s.slice(0, 10)}`}
                  onClick={() => onSend(s)}
                  className="w-full text-left text-xs font-mono text-[#A1A1AA] border border-[#2A2A2A] hover:border-[#FF3B30] hover:text-[#F5F5F5] px-3 py-2 transition-colors"
                >
                  → {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {generating && (
          <div className="flex gap-3 slide-up" data-testid="streaming-bubble">
            <div className="w-7 h-7 bg-[#FF3B30] flex items-center justify-center flex-shrink-0">
              <Sparkle size={14} weight="fill" color="#050505" />
            </div>
            <div className="flex-1 pt-1 min-w-0">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#FF3B30] mb-2">/ assistant</div>
              {cleanStreamingText ? (
                <div className="text-sm text-[#F5F5F5] whitespace-pre-wrap break-words leading-relaxed">
                  {cleanStreamingText}
                  <span className="cursor-blink ml-0.5 text-[#FF3B30]">█</span>
                </div>
              ) : (
                <div className="font-mono text-sm text-[#A1A1AA]">
                  <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> thinking
                  <span className="cursor-blink ml-1">█</span>
                </div>
              )}
              {streamingText?.includes("===FILE:") && (
                <div className="mt-2 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[#FFCC00] border border-[#2A2A2A] px-2 py-1">
                  <Code size={10} weight="bold" /> writing files...
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-[#2A2A2A] p-4 flex-shrink-0 bg-[#050505]">
        <div className="border border-[#2A2A2A] focus-within:border-[#FF3B30] bg-[#0D0D0D] flex items-end gap-2 p-2">
          <textarea
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={generating}
            placeholder="Describe what to build or change..."
            rows={2}
            className="flex-1 bg-transparent text-[#F5F5F5] placeholder-[#52525B] focus:outline-none resize-none px-2 py-1 text-sm font-mono disabled:opacity-50"
          />
          <button
            data-testid="send-prompt-btn"
            type="submit"
            disabled={generating || !input.trim()}
            className="bg-[#FF3B30] text-[#F5F5F5] hover:bg-[#F5F5F5] hover:text-[#050505] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-[#FF3B30] disabled:hover:text-[#F5F5F5] p-2.5 flex-shrink-0"
            title="Send (Enter)"
          >
            <PaperPlaneTilt size={16} weight="bold" />
          </button>
        </div>
        <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[#52525B]">
          enter to send · shift+enter for newline · streaming on
        </div>
      </form>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  const visibleContent = isUser
    ? msg.content
    : msg.content
        ?.replace(/===FILE:[\s\S]*?===END===/g, "")
        .replace(/```[\s\S]*?```/g, "")
        .trim() || "Generated code →";

  return (
    <div className="flex gap-3 slide-up" data-testid={`message-${msg.id}`}>
      <div className={`w-7 h-7 flex items-center justify-center flex-shrink-0 ${isUser ? "bg-[#F5F5F5]" : "bg-[#FF3B30]"}`}>
        {isUser ? <User size={14} weight="bold" color="#050505" /> : <Sparkle size={14} weight="fill" color="#050505" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className={`font-mono text-[10px] uppercase tracking-[0.2em] mb-2 ${isUser ? "text-[#A1A1AA]" : "text-[#FF3B30]"}`}>
          / {isUser ? "user" : "assistant"}
        </div>
        <div className="text-sm text-[#F5F5F5] whitespace-pre-wrap break-words leading-relaxed">{visibleContent}</div>
        {!isUser && (msg.code || msg.files?.length) && (
          <div className="mt-2 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[#FFCC00] border border-[#2A2A2A] px-2 py-1">
            <Code size={10} weight="bold" />
            {msg.files?.length ? `${msg.files.length} file${msg.files.length === 1 ? "" : "s"} generated` : "code generated"}
          </div>
        )}
      </div>
    </div>
  );
}
