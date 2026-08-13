interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = 'Loading…' }: LoadingStateProps) {
  return (
    <div className="state-box">
      <div className="spinner" aria-hidden />
      <p>{label}</p>
    </div>
  );
}
