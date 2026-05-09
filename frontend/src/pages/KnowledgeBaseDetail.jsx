import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient from "@/lib/api";
import { toast } from "sonner";
import HubHeader from "@/components/HubHeader";
import { UploadSimple, Globe, Trash, MagnifyingGlass, FileText, Link as LinkIcon } from "@phosphor-icons/react";

export default function KnowledgeBaseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInput = useRef(null);

  const [kb, setKb] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [url, setUrl] = useState("");
  const [ingestingUrl, setIngestingUrl] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);

  const load = () =>
    Promise.all([apiClient.get(`/knowledge/${id}`), apiClient.get(`/knowledge/${id}/documents`)])
      .then(([k, d]) => { setKb(k.data); setDocs(d.data); })
      .catch(() => { toast.error("Failed to load"); navigate("/knowledge"); })
      .finally(() => setLoading(false));

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const onUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await apiClient.post(`/knowledge/${id}/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDocs((p) => [data, ...p]);
      load();
      toast.success(`Indexed ${data.chunk_count} chunks`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onIngestUrl = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setIngestingUrl(true);
    try {
      const { data } = await apiClient.post(`/knowledge/${id}/url`, { url });
      setDocs((p) => [data, ...p]);
      load();
      setUrl("");
      toast.success(`Indexed ${data.chunk_count} chunks from URL`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "URL fetch failed");
    } finally { setIngestingUrl(false); }
  };

  const deleteDoc = async (docId) => {
    if (!window.confirm("Delete this document and its chunks?")) return;
    try {
      await apiClient.delete(`/knowledge/${id}/documents/${docId}`);
      setDocs(docs.filter((d) => d.id !== docId));
      load();
      toast.success("Deleted");
    } catch { toast.error("Delete failed"); }
  };

  const onSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const { data } = await apiClient.post(`/knowledge/${id}/search`, { query: searchQuery, top_k: 5 });
      setSearchResults(data.results || []);
      if (!data.results?.length) toast.info("No matches found");
    } catch { toast.error("Search failed"); }
    finally { setSearching(false); }
  };

  if (loading || !kb) {
    return (
      <div className="h-screen w-full bg-[#050505] flex items-center justify-center">
        <div className="font-mono text-sm text-[#A1A1AA]"><span className="ascii-pulse">▓▓▓▓▓░░░░░</span> loading kb...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5]" data-testid="kb-detail">
      <HubHeader section={`KB / ${kb.name}`} sectionColor="#34C759" />

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-10 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#34C759] mb-3">/ overview</div>
        <h1 className="font-heading text-3xl sm:text-4xl tracking-tighter font-black leading-[0.95]">{kb.name}</h1>
        {kb.description && <p className="mt-3 text-[#A1A1AA] max-w-2xl">{kb.description}</p>}
        <div className="mt-6 flex gap-6">
          <Stat label="Docs" value={kb.doc_count || 0} />
          <Stat label="Chunks" value={kb.chunk_count || 0} />
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-10 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-3">/ ingest</div>
        <h2 className="font-heading text-2xl tracking-tight font-bold mb-6">Add documents</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
          <div className="bg-[#0D0D0D] border border-[#2A2A2A] p-6">
            <div className="flex items-center gap-3 mb-4">
              <UploadSimple size={20} weight="bold" className="text-[#34C759]" />
              <div className="font-heading font-bold tracking-tight">Upload file</div>
            </div>
            <p className="text-xs text-[#A1A1AA] mb-4">PDF, DOCX, TXT, MD · max 15MB</p>
            <input
              ref={fileInput}
              data-testid="kb-file-input"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => onUpload(e.target.files?.[0])}
              className="hidden"
            />
            <button
              data-testid="kb-upload-btn"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
              className="w-full border border-[#2A2A2A] hover:border-[#34C759] hover:text-[#34C759] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50"
            >
              {uploading ? "Indexing..." : "Choose file"}
            </button>
          </div>

          <form onSubmit={onIngestUrl} className="bg-[#0D0D0D] border border-[#2A2A2A] p-6">
            <div className="flex items-center gap-3 mb-4">
              <Globe size={20} weight="bold" className="text-[#34C759]" />
              <div className="font-heading font-bold tracking-tight">Ingest URL</div>
            </div>
            <p className="text-xs text-[#A1A1AA] mb-4">We'll scrape and index the text content.</p>
            <input
              data-testid="kb-url-input"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="w-full bg-[#050505] border border-[#2A2A2A] focus:border-[#34C759] focus:outline-none text-[#F5F5F5] px-4 py-3 mb-3 font-mono text-sm"
            />
            <button
              data-testid="kb-url-btn"
              type="submit"
              disabled={ingestingUrl || !url.trim()}
              className="w-full bg-[#34C759] text-[#050505] hover:bg-[#F5F5F5] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50"
            >
              {ingestingUrl ? "Fetching..." : "Ingest"}
            </button>
          </form>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-10 border-b border-[#2A2A2A]">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-3">/ search</div>
        <h2 className="font-heading text-2xl tracking-tight font-bold mb-6">Test the index</h2>
        <form onSubmit={onSearch} className="flex gap-2 mb-4">
          <input
            data-testid="kb-search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Ask anything about your documents..."
            className="flex-1 bg-[#050505] border border-[#2A2A2A] focus:border-[#FF3B30] focus:outline-none text-[#F5F5F5] px-4 py-3 font-mono text-sm"
          />
          <button data-testid="kb-search-btn" type="submit" disabled={searching} className="bg-[#FF3B30] text-[#F5F5F5] hover:bg-[#F5F5F5] hover:text-[#050505] font-bold uppercase text-xs tracking-wide px-5 py-3 disabled:opacity-50 flex items-center gap-2">
            <MagnifyingGlass size={14} weight="bold" />
            {searching ? "Searching..." : "Search"}
          </button>
        </form>
        {searchResults.length > 0 && (
          <div className="space-y-3" data-testid="kb-search-results">
            {searchResults.map((r, i) => (
              <div key={i} className="bg-[#0D0D0D] border border-[#2A2A2A] p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">{r.doc_name}</div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#FFCC00]">score: {(r.score || 0).toFixed(3)}</div>
                </div>
                <p className="text-sm text-[#F5F5F5] leading-relaxed">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-10">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA] mb-3">/ documents</div>
        <h2 className="font-heading text-2xl tracking-tight font-bold mb-6">Indexed</h2>
        {docs.length === 0 ? (
          <div className="border border-dashed border-[#2A2A2A] p-8 text-center text-[#A1A1AA] text-sm">
            No documents yet. Upload a file or paste a URL above.
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map((d) => (
              <div key={d.id} className="bg-[#121212] border border-[#2A2A2A] p-4 flex items-center justify-between gap-4" data-testid={`doc-row-${d.id}`}>
                <div className="flex items-center gap-3 min-w-0">
                  {d.source_type === "url" ? <LinkIcon size={16} className="text-[#34C759] flex-shrink-0" /> : <FileText size={16} className="text-[#34C759] flex-shrink-0" />}
                  <div className="min-w-0">
                    <div className="font-mono text-sm truncate">{d.name}</div>
                    <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] mt-0.5">
                      {d.source_type} · {d.chunk_count} chunks · {d.char_count.toLocaleString()} chars · {new Date(d.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <button onClick={() => deleteDoc(d.id)} className="text-[#A1A1AA] hover:text-[#FF3B30] flex-shrink-0" data-testid={`delete-doc-${d.id}`}>
                  <Trash size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">{label}</div>
      <div className="font-heading text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}
