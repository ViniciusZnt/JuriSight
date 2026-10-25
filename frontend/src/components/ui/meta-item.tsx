import type { LucideIcon } from "lucide-react";

interface MetaItemProps {
  icon: LucideIcon;
  children: React.ReactNode;
  className?: string;
  iconClassName?: string;
  iconSize?: string;
  fontSize?: string;
  gap?: string;
}

/** Linha "ícone + texto" curta usada nos metadados da decisão (tribunal, data, processo…). */
export function MetaItem({
  icon: Icon,
  children,
  className = "text-[#6B6B80] dark:text-[#A6A6B4]",
  iconClassName = "text-[#9090A8] dark:text-[#7C7C88]",
  iconSize = "w-3.5 h-3.5",
  fontSize = "13.8px",
  gap = "gap-2",
}: MetaItemProps) {
  return (
    <div className={`flex items-center ${gap} ${className}`} style={{ fontSize }}>
      <Icon className={`${iconSize} flex-shrink-0 ${iconClassName}`} strokeWidth={1.8} />
      {children}
    </div>
  );
}
