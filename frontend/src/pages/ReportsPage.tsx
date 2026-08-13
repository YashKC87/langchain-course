import { useCallback, useEffect, useState } from 'react';
import { Download, FileText, FileType2 } from 'lucide-react';
import { formatApiError } from '../api/client';
import { BrandLogo } from '../components/BrandLogo';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { SectionTile } from '../components/SectionTile';
import { loadReportSnapshot, type ReportSnapshot } from '../utils/reportData';
import { exportReportDocx, exportReportPdf } from '../utils/reportExport';
import { formatNumber, formatRelative } from '../utils/format';

export function ReportsPage() {
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'docx' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ReportSnapshot | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setSnapshot(await loadReportSnapshot());
    } catch (err) {
      setError(formatApiError(err));
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runExport = async (format: 'pdf' | 'docx') => {
    setExporting(format);
    setError(null);
    try {
      const fresh = await loadReportSnapshot();
      setSnapshot(fresh);
      if (format === 'pdf') await exportReportPdf(fresh);
      else await exportReportDocx(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  if (loading && !snapshot) return <LoadingState label="Preparing report data…" />;
  if (error && !snapshot) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="stack">
      <div className="panel report-hero">
        <div className="report-hero-brand">
          <BrandLogo size={56} />
          <div>
            <div className="report-hero-title">Sigma Orion</div>
            <div className="report-hero-subtitle">Operational report export</div>
            <p className="panel-subtitle" style={{ marginTop: 6 }}>
              Generate a branded PDF or Word document with live metering, executions, and attention
              findings. The template includes the Sigma Orion logo and title block.
            </p>
          </div>
        </div>
        <button type="button" className="btn" onClick={() => void load()} disabled={exporting != null}>
          Refresh data
        </button>
      </div>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="section-tile-grid">
        <SectionTile
          title="Export PDF"
          description="A4 report with Sigma Orion header, KPIs, agent metering, and executions"
          icon={FileText}
          value={exporting === 'pdf' ? 'Exporting…' : 'PDF'}
          onClick={exporting ? undefined : () => void runExport('pdf')}
        />
        <SectionTile
          title="Export Word"
          description="Editable .docx using the same Sigma Orion branded template"
          icon={FileType2}
          value={exporting === 'docx' ? 'Exporting…' : 'DOCX'}
          onClick={exporting ? undefined : () => void runExport('docx')}
        />
        <SectionTile
          title="Template contents"
          description="Logo · Sigma Orion · KPIs · Metering · Executions · Needs Attention"
          icon={Download}
          value="Included"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Report preview snapshot</h2>
            <p className="panel-subtitle">
              {snapshot
                ? `Last prepared ${formatRelative(snapshot.generatedAt)} · ${snapshot.status.agents} agents · ${snapshot.status.executions} executions`
                : 'No snapshot yet'}
            </p>
          </div>
        </div>
        {!snapshot ? (
          <EmptyState title="No report data" message="Refresh to load live telemetry into the template." compact />
        ) : (
          <div className="section-tile-grid">
            <SectionTile
              title="Active Agents"
              value={formatNumber(snapshot.kpis?.active_agents?.value ?? null)}
            />
            <SectionTile
              title="Executions"
              value={formatNumber(snapshot.kpis?.executions?.value ?? null)}
            />
            <SectionTile
              title="Total Tokens"
              value={formatNumber(snapshot.kpis?.total_tokens?.value ?? null)}
            />
            <SectionTile
              title="Attention items"
              value={formatNumber(snapshot.attention.length || null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
