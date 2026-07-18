import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { AgentPage } from "./pages/AgentPage";
import { PrecheckPage } from "./pages/PrecheckPage";
import { RegulationsPage } from "./pages/RegulationsPage";
import { AuditPage } from "./pages/AuditPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/regulations" element={<RegulationsPage />} />
        <Route path="/precheck" element={<PrecheckPage />} />
        <Route path="/agent" element={<AgentPage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Routes>
    </AppShell>
  );
}
