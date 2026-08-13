import type { MetricValue } from '../types';
import { formatDuration, formatNumber, formatPercent } from '../utils/format';

interface MetricCardProps {
  label: string;
  metric?: MetricValue | null;
  value?: number | null;
  available?: boolean;
  format?: 'number' | 'percent' | 'duration' | 'raw';
  unit?: string;
  subtitle?: string;
  displayValue?: string | null;
  onClick?: () => void;
}

export function MetricCard({
  label,
  metric,
  value,
  available,
  format = 'number',
  unit,
  subtitle,
  displayValue,
  onClick,
}: MetricCardProps) {
  const isAvailable = displayValue != null && displayValue !== ''
    ? true
    : metric
      ? metric.available && metric.value != null
      : available === true && value != null;
  const raw = metric ? metric.value : value;

  let display = '—';
  if (displayValue != null && displayValue !== '') {
    display = displayValue;
  } else if (isAvailable && raw != null) {
    if (format === 'percent') display = formatPercent(raw);
    else if (format === 'duration') display = formatDuration(raw);
    else if (format === 'raw') display = String(raw);
    else display = formatNumber(raw);
    if (unit && format !== 'percent' && format !== 'duration') display = `${display}${unit}`;
  }

  const sub =
    !isAvailable || (displayValue == null && raw == null && !displayValue)
      ? metric?.label || subtitle || 'No live data'
      : subtitle ?? metric?.unit ?? null;

  const interactive = typeof onClick === 'function';
  const Tag = interactive ? 'button' : 'div';

  return (
    <Tag
      type={interactive ? 'button' : undefined}
      className={`metric-card${interactive ? ' interactive' : ''}`}
      onClick={onClick}
    >
      <div className="metric-label">{label}</div>
      <div className={`metric-value${isAvailable ? '' : ' unavailable'}`}>{display}</div>
      {sub ? <div className="metric-sub">{sub}</div> : null}
    </Tag>
  );
}
