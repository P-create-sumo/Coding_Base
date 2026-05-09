import { Link, useNavigate } from "react-router-dom";
import { Lightning, House, CaretRight, SignOut } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";
import { useState } from "react";

export default function HubHeader({ section, sectionColor = "#FF3B30", children }) {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-50 bg-[#050505]/80 backdrop-blur-xl border-b border-[#2A2A2A]">
      <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/" className="flex items-center gap-3 flex-shrink-0">
            <div className="w-9 h-9 bg-[#FF3B30] flex items-center justify-center">
              <Lightning size={20} weight="fill" color="#050505" />
            </div>
            <div className="hidden sm:block">
              <div className="font-heading font-black text-lg tracking-tighter leading-none">FORGE</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] leading-none mt-0.5">/ ai platform</div>
            </div>
          </Link>
          <CaretRight size={14} className="text-[#52525B] hidden sm:block" />
          <Link to="/" className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] hover:text-[#F5F5F5] hidden sm:flex items-center gap-1">
            <House size={12} /> hub
          </Link>
          <CaretRight size={14} className="text-[#52525B]" />
          <span className="font-mono text-xs uppercase tracking-[0.2em] font-bold truncate" style={{ color: sectionColor }}>
            {section}
          </span>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {children}
          <UserDropdown user={user} onLogout={logout} />
        </div>
      </div>
    </header>
  );
}

function UserDropdown({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const initial = user.name?.[0]?.toUpperCase() || "U";
  return (
    <div className="relative">
      <button
        data-testid="user-menu-btn"
        onClick={() => setOpen(!open)}
        className="w-9 h-9 bg-[#121212] border border-[#2A2A2A] hover:border-[#FF3B30] flex items-center justify-center overflow-hidden"
      >
        {user.picture ? (
          <img src={user.picture} alt={user.name} className="w-full h-full object-cover" />
        ) : (
          <span className="font-bold text-sm">{initial}</span>
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
