import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface SectionTileProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  value?: ReactNode;
  meta?: ReactNode;
  tone?: 'default' | 'running' | 'success' | 'warning' | 'failed';
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

export function SectionTile({
  title,
  description,
  icon: Icon,
  value,
  meta,
  tone = 'default',
  selected = false,
  onClick,
  className = '',
}: SectionTileProps) {
  const interactive = typeof onClick === 'function';
  const Tag = interactive ? 'button' : 'div';

  return (
    <Tag
      type={interactive ? 'button' : undefined}
      className={`section-tile tone-${tone}${selected ? ' selected' : ''}${interactive ? ' interactive' : ''} ${className}`.trim()}
      onClick={onClick}
    >
      <div className="section-tile-top">
        {Icon ? (
          <span className="section-tile-icon" aria-hidden>
            <Icon size={18} strokeWidth={1.75} />
          </span>
        ) : null}
        <div className="section-tile-copy">
          <div className="section-tile-title">{title}</div>
          {description ? <div className="section-tile-desc">{description}</div> : null}
        </div>
      </div>
      {value != null ? <div className="section-tile-value">{value}</div> : null}
      {meta != null ? <div className="section-tile-meta">{meta}</div> : null}
    </Tag>
  );
}
