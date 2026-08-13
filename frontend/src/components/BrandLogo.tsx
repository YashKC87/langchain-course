interface BrandLogoProps {
  size?: number;
  className?: string;
}

/** Reversed Sigma mark — white Σ on a solid red circle. */
export function BrandLogo({ size = 36, className = '' }: BrandLogoProps) {
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
      <circle cx="32" cy="32" r="30" fill="#E31C23" />
      <path
        d="M18 18h28l-18 14 18 14H18"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
