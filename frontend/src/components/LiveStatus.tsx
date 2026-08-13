interface LiveStatusProps {
  live: boolean;
  label?: string;
}

export function LiveStatus({ live, label }: LiveStatusProps) {
  return (
    <span className={`live-status ${live ? 'live' : 'waiting'}`} title={label}>
      <span className="live-dot" aria-hidden />
      {live ? 'LIVE' : 'WAITING'}
    </span>
  );
}
