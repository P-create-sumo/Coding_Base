import { Lightning, GoogleLogo, ArrowRight } from "@phosphor-icons/react";

export default function LoginPage() {
  const handleLogin = () => {
    const redirectUrl = window.location.origin + "/Coding_Base/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#F5F5F5] flex flex-col" data-testid="login-page">
      {/* Header */}
      <header className="border-b border-[#2A2A2A] px-6 md:px-8 lg:px-12 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-[#FF3B30] flex items-center justify-center">
            <Lightning size={20} weight="fill" color="#050505" />
          </div>
          <div>
            <div className="font-heading font-black text-lg tracking-tighter leading-none">FORGE</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA] leading-none mt-0.5">/ ai app builder</div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 grid grid-cols-1 md:grid-cols-12">
        <div className="md:col-span-7 flex items-center px-6 md:px-12 lg:px-20 py-12 border-r border-[#2A2A2A]">
          <div className="max-w-xl">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FF3B30] mb-6 flex items-center gap-2">
              <span className="w-2 h-2 bg-[#FF3B30] rounded-full ascii-pulse" />
              <span>welcome / sign in to continue</span>
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black leading-[0.95]">
              Build apps<br />
              by <span className="text-[#FF3B30]">describing</span> them.
            </h1>
            <p className="mt-6 text-base md:text-lg text-[#A1A1AA] max-w-lg leading-relaxed">
              Sign in with Google to access your projects, version history, and instant exports.
            </p>

            <button
              data-testid="google-login-btn"
              onClick={handleLogin}
              className="mt-10 bg-[#F5F5F5] text-[#050505] hover:bg-[#FF3B30] hover:text-[#F5F5F5] font-bold uppercase text-sm tracking-wide px-7 py-4 flex items-center gap-3"
            >
              <GoogleLogo size={18} weight="bold" />
              Continue with Google
              <ArrowRight size={16} weight="bold" />
            </button>

            <div className="mt-8 font-mono text-[10px] uppercase tracking-[0.2em] text-[#52525B]">
              by signing in you agree to our terms / cookies are required
            </div>
          </div>
        </div>

        <div className="hidden md:flex md:col-span-5 items-center justify-center bg-[#0D0D0D] p-12">
          <div className="w-full max-w-md">
            <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#FFCC00] mb-6">/ powered by</div>
            <div className="space-y-4">
              <Stat label="LLM" value="Claude Sonnet 4.5" />
              <Stat label="Streaming" value="Real-time" />
              <Stat label="Versions" value="20 per project" />
              <Stat label="Export" value=".zip / Vite ready" />
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-[#2A2A2A] px-6 md:px-8 lg:px-12 py-4">
        <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#A1A1AA]">
          © {new Date().getFullYear()} forge / built with claude sonnet 4.5
        </div>
      </footer>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="border-b border-[#2A2A2A] pb-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#A1A1AA]">{label}</div>
      <div className="font-heading text-xl font-bold tracking-tight mt-1">{value}</div>
    </div>
  );
}
