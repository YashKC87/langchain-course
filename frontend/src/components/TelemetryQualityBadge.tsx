import type { TelemetryQuality } from '../types';
import { statusTone } from '../utils/format';

interface TelemetryQualityBadgeProps {
  quality: TelemetryQuality | string | null | undefined;
}

export function TelemetryQualityBadge({ quality }: TelemetryQualityBadgeProps) {
  const tone = statusTone(quality);
  const label = quality?.replace(/_/g, ' ') || 'unknown';
  return <span className={`badge ${tone}`}>{label}</span>;
}
