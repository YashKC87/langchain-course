import { useFilters } from '../hooks/useFilters';

const FILTERS: Array<{ key: keyof ReturnType<typeof useFilters>['filters']; label: string; options?: string[] }> = [
  { key: 'cloud', label: 'Cloud', options: ['azure', 'aws', 'gcp', 'multi'] },
  { key: 'platform', label: 'Platform' },
  { key: 'tenant', label: 'Tenant' },
  { key: 'business_unit', label: 'Business Unit' },
  { key: 'environment', label: 'Environment', options: ['prod', 'staging', 'dev'] },
  { key: 'agent', label: 'Agent' },
  { key: 'framework', label: 'Framework' },
  { key: 'model', label: 'Model' },
  { key: 'status', label: 'Status', options: ['running', 'success', 'failed', 'warning'] },
  { key: 'time_range', label: 'Time', options: ['15m', '1h', '6h', '24h', '7d'] },
];

export function GlobalFilterBar() {
  const { filters, setFilter, resetFilters, activeCount } = useFilters();

  return (
    <div className="filter-bar">
      {FILTERS.map((f) =>
        f.options ? (
          <select
            key={f.key}
            className="select"
            value={filters[f.key]}
            aria-label={f.label}
            onChange={(e) => setFilter(f.key, e.target.value)}
          >
            <option value="">{f.key === 'time_range' ? 'Time: 1h' : f.label}</option>
            {f.options.map((o) => (
              <option key={o} value={o}>
                {f.key === 'time_range' ? o : o}
              </option>
            ))}
          </select>
        ) : (
          <input
            key={f.key}
            className="input"
            style={{ width: 120 }}
            placeholder={f.label}
            value={filters[f.key]}
            aria-label={f.label}
            onChange={(e) => setFilter(f.key, e.target.value)}
          />
        ),
      )}
      {activeCount > 0 ? (
        <button type="button" className="btn btn-ghost" onClick={resetFilters}>
          Clear ({activeCount})
        </button>
      ) : null}
    </div>
  );
}
