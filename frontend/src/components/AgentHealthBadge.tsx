import type { AgentHealth } from '../types';
import { statusTone } from '../utils/format';

interface AgentHealthBadgeProps {
  health: AgentHealth | string | null | undefined;
}

export function AgentHealthBadge({ health }: AgentHealthBadgeProps) {
  const tone = statusTone(health);
  const label = health?.replace(/_/g, ' ') || 'unknown';
  return <span className={`badge ${tone}`}>{label}</span>;
}
