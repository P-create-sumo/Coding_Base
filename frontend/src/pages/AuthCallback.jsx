import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import apiClient, { getLegacyUserId, clearLegacyUserId } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/login");
      return;
    }

    const sessionId = match[1];

    (async () => {
      try {
        const { data } = await apiClient.post("/auth/session", { session_id: sessionId });
        setUser(data.user);

        // Migrate localStorage projects if any
        const legacy = getLegacyUserId();
        if (legacy) {
          try {
            const r = await apiClient.post("/auth/migrate", { legacy_user_id: legacy });
            if (r.data?.migrated > 0) {
              toast.success(`Imported ${r.data.migrated} previous project${r.data.migrated === 1 ? "" : "s"}`);
            }
          } catch (e) {
            console.error("Migration failed", e);
          }
          clearLegacyUserId();
        }

        // Clean URL fragment
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/", { state: { user: data.user }, replace: true });
      } catch (e) {
        console.error(e);
        toast.error("Login failed");
        navigate("/login");
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="h-screen w-full bg-[#050505] flex items-center justify-center" data-testid="auth-callback">
      <div className="font-mono text-sm text-[#A1A1AA]">
        <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> signing you in...
      </div>
    </div>
  );
}
