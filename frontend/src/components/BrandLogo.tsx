interface BrandLogoProps {
  size?: number;
  className?: string;
}

/** Red Σ outline in a red circle on white — Sigma Orion brand mark. */
export function BrandLogo({ size = 40, className = '' }: BrandLogoProps) {
  return (
    <img
      src="/sigma-logo.svg"
      width={size}
      height={size}
      alt="Sigma Orion"
      className={`brand-logo ${className}`.trim()}
      draggable={false}
    />
  );
}
