interface BrandLogoProps {
  size?: number;
  className?: string;
}

/** Red Σ in a red circle — matches the brand mark (outline on white). */
export function BrandLogo({ size = 40, className = '' }: BrandLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={`brand-logo ${className}`.trim()}
      role="img"
      aria-label="Sigma Orion"
    >
      <circle
        cx="32"
        cy="32"
        r="28"
        fill="none"
        stroke="#E31C23"
        strokeWidth="3.5"
      />
      {/* Standard upright Σ — top bar, middle peak, bottom bar */}
      <path
        d="M20 19 H44 L32 32 L44 45 H20"
        fill="none"
        stroke="#E31C23"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
