import { useFilters } from '../hooks/useFilters';

type FilterKey = keyof ReturnType<typeof useFilters>['filters'];

const FILTERS: Array<{
  key: FilterKey;
  label: string;
  options?: string[];
  width?: number;
}> = [
  { key: 'cloud', label: 'Cloud', options: ['azure', 'aws', 'gcp', 'local', 'other'] },
  { key: 'platform', label: 'Platform', width: 130 },
  { key: 'tenant', label: 'Tenant / Account', width: 150 },
  { key: 'business_unit', label: 'Business Unit', width: 130 },
  { key: 'environment', label: 'Environment', options: ['prod', 'staging', 'dev'] },
  { key: 'agent', label: 'Agent', width: 130 },
  { key: 'framework', label: 'Framework', width: 120 },
  { key: 'model', label: 'Model', width: 120 },
  { key: 'status', label: 'Status', options: ['running', 'success', 'failed', 'warning'] },
  { key: 'time_range', label: 'Time Range', options: ['15m', '1h', '6h', '24h', '7d'] },
];

export function GlobalFilterBar() {
  const { filters, setFilter, resetFilters, activeCount } = useFilters();

  return (
    <div className="filter-bar" role="toolbar" aria-label="Global filters">
      <div className="filter-bar-scroll">
        {FILTERS.map((f) => (
          <label key={f.key} className="filter-field">
            <span className="filter-field-label">{f.label}</span>
            {f.options ? (
              <select
                className="select filter-control"
                value={filters[f.key]}
                aria-label={f.label}
                onChange={(e) => setFilter(f.key, e.target.value)}
              >
                <option value="">{f.key === 'time_range' ? '1h' : 'All'}</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="input filter-control"
                style={{ width: f.width ?? 120 }}
                placeholder="Any"
                value={filters[f.key]}
                aria-label={f.label}
                onChange={(e) => setFilter(f.key, e.target.value)}
              />
            )}
          </label>
        ))}
      </div>
      {activeCount > 0 ? (
        <button type="button" className="btn btn-ghost filter-clear" onClick={resetFilters}>
          Clear ({activeCount})
        </button>
      ) : null}
    </div>
  );
}
