import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HubHome from "@/pages/HubHome";
import AppsHub from "@/pages/AppsHub";
import Workspace from "@/pages/Workspace";
import AgentsHub from "@/pages/AgentsHub";
import AgentChat from "@/pages/AgentChat";
import KnowledgeHub from "@/pages/KnowledgeHub";
import KnowledgeBaseDetail from "@/pages/KnowledgeBaseDetail";
import { Toaster } from "sonner";

function App() {
  return (
    <div className="App">
      <BrowserRouter basename="/Coding_Base">
        <Routes>
          <Route path="/" element={<HubHome />} />
          <Route path="/apps" element={<AppsHub />} />
          <Route path="/apps/:id" element={<Workspace />} />
          <Route path="/agents" element={<AgentsHub />} />
          <Route path="/agents/:id" element={<AgentChat />} />
          <Route path="/knowledge" element={<KnowledgeHub />} />
          <Route path="/knowledge/:id" element={<KnowledgeBaseDetail />} />
        </Routes>
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
