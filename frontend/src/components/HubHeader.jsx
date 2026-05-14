import { Link } from "react-router-dom";
import { Lightning, House, CaretRight } from "@phosphor-icons/react";

export default function HubHeader({ section, sectionColor = "#FF3B30", children }) {
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
        </div>
      </div>
    </header>
  );
}
