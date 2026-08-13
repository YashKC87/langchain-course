interface BrandLogoProps {
  size?: number;
  className?: string;
}

/** Reference-faithful Sigma Orion mark (vector SVG). */
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
