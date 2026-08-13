import { useCallback, useEffect, useRef, useState } from 'react';

export type RefreshInterval = 0 | 30 | 60 | 300;

const INTERVAL_LABELS: Record<RefreshInterval, string> = {
  0: 'Manual',
  30: '30s',
  60: '1m',
  300: '5m',
};

export function useAutoRefresh(refreshFn: () => void | Promise<void>, defaultInterval: RefreshInterval = 30) {
  const [intervalSec, setIntervalSec] = useState<RefreshInterval>(defaultInterval);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const fnRef = useRef(refreshFn);
  fnRef.current = refreshFn;

  const run = useCallback(async () => {
    setRefreshing(true);
    try {
      await fnRef.current();
      setLastUpdated(new Date());
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void run();
  }, [run]);

  useEffect(() => {
    if (intervalSec === 0) return;
    const id = window.setInterval(() => {
      void run();
    }, intervalSec * 1000);
    return () => window.clearInterval(id);
  }, [intervalSec, run]);

  return {
    intervalSec,
    setIntervalSec,
    lastUpdated,
    refreshing,
    refresh: run,
    intervalLabel: INTERVAL_LABELS[intervalSec],
    intervalOptions: [
      { value: 30 as RefreshInterval, label: '30s' },
      { value: 60 as RefreshInterval, label: '1m' },
      { value: 300 as RefreshInterval, label: '5m' },
      { value: 0 as RefreshInterval, label: 'Manual' },
    ],
  };
}
