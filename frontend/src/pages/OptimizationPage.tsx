import { useCallback, useState } from 'react';
import { api } from '../api/client';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import type { OptimizationFinding } from '../types';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { OptimizationPanel } from '../components/OptimizationPanel';

export function OptimizationPage() {
  const [items, setItems] = useState<OptimizationFinding[]>([]);
  const [empty, setEmpty] = useState<{ title: string; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getOptimization();
      if (res.empty) {
        setEmpty({ title: res.title ?? 'No optimization findings', message: res.message ?? 'No live data' });
        setItems([]);
      } else {
        setEmpty(null);
        setItems(res.items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load optimization');
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 60);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Optimization</h2>
          <p className="panel-subtitle">
            Evidence-backed recommendations from live telemetry — never synthetic baselines
          </p>
        </div>
      </div>
      <OptimizationPanel
        items={items}
        emptyTitle={empty?.title}
        emptyMessage={empty?.message}
      />
    </div>
  );
}
