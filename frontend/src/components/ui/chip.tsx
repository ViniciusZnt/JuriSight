import type { LucideIcon } from "lucide-react";

type Tone = "amber" | "blue" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  amber: "bg-[#FBF4EC] dark:bg-[#2A2015] border-[#EDD9BC] dark:border-[#4A3A22] text-[#6B3B0A] dark:text-[#E0AC6C]",
  blue: "bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]",
  neutral: "bg-white dark:bg-[#17171B] border-[#E0E0EA] dark:border-[#2A2A32] text-[#4A4A5A] dark:text-[#C4C4CE]",
};

interface ChipProps {
  children: React.ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
  /** "md" = chip de tag/entidade em destaque; "sm" = chip compacto nos cards de resultado. */
  size?: "sm" | "md";
}

/** Pílula pequena para tags e entidades correspondentes. */
export function Chip({ children, tone = "neutral", icon: Icon, size = "md" }: ChipProps) {
  const padding = size === "md" ? "px-2.5 py-1" : "px-2 py-0.5";
  const fontSize = size === "md" ? "12.6px" : "12.1px";
  const rounded = size === "md" ? "rounded-lg" : "rounded";

  return (
    <span className={`inline-flex items-center gap-1 border ${rounded} ${padding} ${TONE_CLASSES[tone]}`} style={{ fontSize, fontWeight: 500 }}>
      {Icon && <Icon className="w-3 h-3" strokeWidth={2} />}
      {children}
    </span>
  );
}
