import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { GlobalFilters } from '../types';

const DEFAULT_FILTERS: GlobalFilters = {
  cloud: '',
  platform: '',
  tenant: '',
  business_unit: '',
  environment: '',
  agent: '',
  framework: '',
  model: '',
  status: '',
  time_range: '1h',
};

interface FiltersContextValue {
  filters: GlobalFilters;
  setFilter: <K extends keyof GlobalFilters>(key: K, value: GlobalFilters[K]) => void;
  setFilters: (next: Partial<GlobalFilters>) => void;
  resetFilters: () => void;
  activeCount: number;
}

const FiltersContext = createContext<FiltersContextValue | null>(null);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFiltersState] = useState<GlobalFilters>(DEFAULT_FILTERS);

  const setFilter = useCallback(<K extends keyof GlobalFilters>(key: K, value: GlobalFilters[K]) => {
    setFiltersState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const setFilters = useCallback((next: Partial<GlobalFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...next }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS);
  }, []);

  const activeCount = useMemo(
    () =>
      Object.entries(filters).filter(([k, v]) => {
        if (k === 'time_range') return v !== '1h';
        return Boolean(v);
      }).length,
    [filters],
  );

  const value = useMemo(
    () => ({ filters, setFilter, setFilters, resetFilters, activeCount }),
    [filters, setFilter, setFilters, resetFilters, activeCount],
  );

  return createElement(FiltersContext.Provider, { value }, children);
}

export function useFilters(): FiltersContextValue {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error('useFilters must be used within FiltersProvider');
  return ctx;
}

export { DEFAULT_FILTERS };
