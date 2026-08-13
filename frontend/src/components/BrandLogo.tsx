interface BrandLogoProps {
  size?: number;
  className?: string;
}

/** Red Sigma (Σ) in a circle — brand mark for the Control Center. */
export function BrandLogo({ size = 36, className = '' }: BrandLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={`brand-logo ${className}`.trim()}
      role="img"
      aria-label="Sigma logo"
    >
      <circle cx="32" cy="32" r="28" fill="none" stroke="#E31C23" strokeWidth="4" />
      <path
        d="M18 18h28l-18 14 18 14H18"
        fill="none"
        stroke="#E31C23"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
