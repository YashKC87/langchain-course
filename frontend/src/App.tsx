import { useCallback, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { api } from './api/client';
import { Layout } from './components/Layout';
import { useAutoRefresh } from './hooks/useAutoRefresh';
import { A2APage } from './pages/A2APage';
import { AgentDetailPage } from './pages/AgentDetailPage';
import { AgentsPage } from './pages/AgentsPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { LiveExecutionsPage } from './pages/LiveExecutionsPage';
import { ModelsPage } from './pages/ModelsPage';
import { ObservabilityPage } from './pages/ObservabilityPage';
import { OptimizationPage } from './pages/OptimizationPage';
import { OverviewPage } from './pages/OverviewPage';
import { RagPage } from './pages/RagPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { ToolsMcpPage } from './pages/ToolsMcpPage';
import { WorkflowPage } from './pages/WorkflowPage';

export default function App() {
  const [live, setLive] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await api.getStatus();
      setLive(Boolean(status.telemetry_live));
    } catch {
      setLive(false);
    }
  }, []);

  const {
    intervalSec,
    setIntervalSec,
    lastUpdated,
    refreshing,
    refresh,
    intervalOptions,
  } = useAutoRefresh(refreshStatus, 30);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Layout
              live={live}
              lastUpdated={lastUpdated}
              refreshing={refreshing}
              onRefresh={() => void refresh()}
              intervalSec={intervalSec}
              setIntervalSec={setIntervalSec}
              intervalOptions={intervalOptions}
            />
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="agents/:agentId" element={<AgentDetailPage />} />
          <Route path="live-executions" element={<LiveExecutionsPage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="tools-mcp" element={<ToolsMcpPage />} />
          <Route path="rag" element={<RagPage />} />
          <Route path="a2a" element={<A2APage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="observability" element={<ObservabilityPage />} />
          <Route path="optimization" element={<OptimizationPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
