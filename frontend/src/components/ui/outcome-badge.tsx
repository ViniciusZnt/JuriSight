import { OUTCOME_CONFIG, type Outcome } from "@/lib/outcome";

interface OutcomeBadgeProps {
  outcome: Outcome;
  /** "md" = badge de destaque no topo da decisão; "sm" = badge compacto nos cards de resultado. */
  size?: "sm" | "md";
  suffix?: string;
}

export function OutcomeBadge({ outcome, size = "sm", suffix = "" }: OutcomeBadgeProps) {
  const config = OUTCOME_CONFIG[outcome];
  const Icon = config.icon;
  const padding = size === "md" ? "px-3 py-1.5" : "px-2.5 py-1";
  const iconSize = size === "md" ? "w-4 h-4" : "w-3 h-3";
  const fontSize = size === "md" ? "13.8px" : "12.6px";

  return (
    <div className={`flex items-center gap-1.5 rounded-full border ${padding} ${config.bg} ${config.border}`}>
      <Icon className={`${iconSize} ${config.text}`} strokeWidth={2} />
      <span className={config.text} style={{ fontSize, fontWeight: 600 }}>
        {config.label}
        {suffix}
      </span>
    </div>
  );
}
