"use client";

import type { LucideIcon } from "lucide-react";

type Tone = "neutral" | "accent" | "success";

const TONE_CLASSES: Record<Tone, string> = {
  neutral:
    "bg-[#FAFAFA] dark:bg-[#1C1C21] border-[#EBEBF2] dark:border-[#26262C] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30",
  accent: "bg-[#EFF4FA] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]",
  success: "bg-[#EDF7F2] dark:bg-[#122A1E] border-[#BDE0CF] dark:border-[#1E4A34] text-[#1A5C3A] dark:text-[#6FCB9A]",
};

const SIZE_CLASSES = {
  md: { padding: "px-3.5 py-2", fontSize: "14.4px" },
  sm: { padding: "px-2.5 py-1.5", fontSize: "13.2px" },
};

interface ActionButtonProps {
  icon: LucideIcon;
  label: string;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  tone?: Tone;
  size?: "sm" | "md";
  iconFill?: boolean;
  title?: string;
  className?: string;
}

/** Botão de ação em pílula (Salvar, Compartilhar, Baixar, Copiar…) com estado neutro/destaque/sucesso. */
export function ActionButton({
  icon: Icon,
  label,
  onClick,
  tone = "neutral",
  size = "md",
  iconFill = false,
  title,
  className = "",
}: ActionButtonProps) {
  const { padding, fontSize } = SIZE_CLASSES[size];
  return (
    <button
      onClick={onClick}
      title={title}
      className={`flex items-center gap-2 ${padding} rounded-lg border transition-all ${TONE_CLASSES[tone]} ${className}`}
      style={{ fontSize, fontWeight: tone === "neutral" ? 400 : 500 }}
    >
      <Icon className="w-3.5 h-3.5" strokeWidth={1.8} fill={iconFill ? "currentColor" : "none"} />
      {label}
    </button>
  );
}
