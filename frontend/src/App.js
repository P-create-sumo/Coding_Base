import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import HubHome from "@/pages/HubHome";
import AppsHub from "@/pages/AppsHub";
import Workspace from "@/pages/Workspace";
import AgentsHub from "@/pages/AgentsHub";
import AgentChat from "@/pages/AgentChat";
import KnowledgeHub from "@/pages/KnowledgeHub";
import KnowledgeBaseDetail from "@/pages/KnowledgeBaseDetail";
import LoginPage from "@/pages/LoginPage";
import AuthCallback from "@/pages/AuthCallback";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Toaster } from "sonner";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-screen w-full bg-[#050505] flex items-center justify-center">
        <div className="font-mono text-sm text-[#A1A1AA]">
          <span className="ascii-pulse">▓▓▓▓▓░░░░░</span> verifying session...
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><HubHome /></ProtectedRoute>} />
      <Route path="/apps" element={<ProtectedRoute><AppsHub /></ProtectedRoute>} />
      <Route path="/apps/:id" element={<ProtectedRoute><Workspace /></ProtectedRoute>} />
      <Route path="/agents" element={<ProtectedRoute><AgentsHub /></ProtectedRoute>} />
      <Route path="/agents/:id" element={<ProtectedRoute><AgentChat /></ProtectedRoute>} />
      <Route path="/knowledge" element={<ProtectedRoute><KnowledgeHub /></ProtectedRoute>} />
      <Route path="/knowledge/:id" element={<ProtectedRoute><KnowledgeBaseDetail /></ProtectedRoute>} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter basename="/Coding_Base">
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#121212",
            color: "#F5F5F5",
            border: "1px solid #2A2A2A",
            borderRadius: 0,
            fontFamily: "IBM Plex Sans, sans-serif",
          },
        }}
      />
    </div>
  );
}

export default App;
