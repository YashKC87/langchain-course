import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Activity,
  Boxes,
  BrainCircuit,
  Cable,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Network,
  Radio,
  Settings,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { FiltersProvider } from '../hooks/useFilters';
import { GlobalFilterBar } from './GlobalFilterBar';
import { LiveStatus } from './LiveStatus';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/agents', label: 'Agents', icon: Boxes },
  { to: '/live-executions', label: 'Live Executions', icon: Radio },
  { to: '/workflow', label: 'Workflow', icon: GitBranch },
  { to: '/models', label: 'Models', icon: BrainCircuit },
  { to: '/tools-mcp', label: 'Tools & MCP', icon: Wrench },
  { to: '/rag', label: 'RAG', icon: Network },
  { to: '/a2a', label: 'Multi-Agent / A2A', icon: Cable },
  { to: '/integrations', label: 'Integrations', icon: Cable },
  { to: '/observability', label: 'Observability', icon: Activity },
  { to: '/optimization', label: 'Optimization', icon: Sparkles },
  { to: '/settings', label: 'Settings', icon: Settings },
];

const TITLES: Record<string, string> = {
  '/': 'Overview',
  '/agents': 'Agents',
  '/live-executions': 'Live Executions',
  '/workflow': 'Workflow',
  '/models': 'Models',
  '/tools-mcp': 'Tools & MCP',
  '/rag': 'RAG',
  '/a2a': 'Multi-Agent / A2A',
  '/integrations': 'Integrations',
  '/observability': 'Observability',
  '/optimization': 'Optimization',
  '/settings': 'Settings',
};

interface LayoutProps {
  live: boolean;
  lastUpdated: Date | null;
  refreshing: boolean;
  onRefresh: () => void;
  intervalSec: number;
  setIntervalSec: (v: 0 | 30 | 60 | 300) => void;
  intervalOptions: Array<{ value: 0 | 30 | 60 | 300; label: string }>;
}

export function Layout({
  live,
  lastUpdated,
  refreshing,
  onRefresh,
  intervalSec,
  setIntervalSec,
  intervalOptions,
}: LayoutProps) {
  const location = useLocation();
  const title =
    TITLES[location.pathname] ??
    (location.pathname.startsWith('/agents/') ? 'Agent Detail' : 'Control Center');

  return (
    <FiltersProvider>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="sidebar-brand-mark">Control Center</div>
            <div className="sidebar-brand-title">Agent Metering &amp; Observability</div>
          </div>
          <nav className="sidebar-nav">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                <item.icon size={16} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="main-area">
          <header className="top-header">
            <div className="top-header-row">
              <h1 className="page-title">{title}</h1>
              <div className="header-actions">
                <LiveStatus live={live} />
                <div className="refresh-controls">
                  <select
                    className="select"
                    value={intervalSec}
                    aria-label="Auto refresh interval"
                    onChange={(e) => setIntervalSec(Number(e.target.value) as 0 | 30 | 60 | 300)}
                  >
                    {intervalOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        Refresh {o.label}
                      </option>
                    ))}
                  </select>
                  <button type="button" className="btn" onClick={onRefresh} disabled={refreshing}>
                    {refreshing ? 'Refreshing…' : 'Refresh'}
                  </button>
                  <span>
                    {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Not updated'}
                  </span>
                </div>
                <Gauge size={16} className="muted" aria-hidden />
              </div>
            </div>
            <GlobalFilterBar />
          </header>
          <main className="page-content">
            <Outlet />
          </main>
        </div>
      </div>
    </FiltersProvider>
  );
}
