interface IntegrationSwitchProps {
  enabled: boolean;
  disabled?: boolean;
  onChange: (enabled: boolean) => void;
  ariaLabel?: string;
}

export function IntegrationSwitch({ enabled, disabled, onChange, ariaLabel }: IntegrationSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={ariaLabel ?? (enabled ? 'Disable integration' : 'Enable integration')}
      className={`switch${enabled ? ' on' : ''}`}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
    >
      <span className="switch-knob" />
    </button>
  );
}
