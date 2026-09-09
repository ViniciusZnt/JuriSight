import { ThumbsUp, ThumbsDown, Info, type LucideIcon } from "lucide-react";
import type { Provimento } from "@/lib/api";

export type Outcome = "favorable" | "unfavorable" | "neutral";

/** Mapeia o provimento real (backend) para o Outcome visual (3 estados). PARCIAL
 *  e NAO_APLICAVEL (súmulas/OJs, que não julgam um pedido) caem em "neutral" —
 *  nem favorável nem desfavorável de forma inequívoca. */
export function provimentoToOutcome(provimento: Provimento): Outcome {
  switch (provimento) {
    case "APROVADO":
      return "favorable";
    case "NEGADO":
      return "unfavorable";
    case "PARCIAL":
    case "NAO_APLICAVEL":
      return "neutral";
  }
}

interface OutcomeConfig {
  label: string;
  icon: LucideIcon;
  bg: string;
  border: string;
  text: string;
  dot: string;
}

/** Estilo único por resultado (favorável/desfavorável/neutro), usado no badge da decisão e nos cards de resultados. */
export const OUTCOME_CONFIG: Record<Outcome, OutcomeConfig> = {
  favorable: {
    label: "Favorável",
    icon: ThumbsUp,
    bg: "bg-[#EDF7F2] dark:bg-[#122A1E]",
    border: "border-[#BDE0CF] dark:border-[#1E4A34]",
    text: "text-[#1A5C3A] dark:text-[#6FCB9A]",
    dot: "bg-[#2D8A5F] dark:bg-[#3DA372]",
  },
  unfavorable: {
    label: "Desfavorável",
    icon: ThumbsDown,
    bg: "bg-[#FBF0F0] dark:bg-[#2A1517]",
    border: "border-[#E8C2C2] dark:border-[#4A2529]",
    text: "text-[#7A1A1A] dark:text-[#E08A93]",
    dot: "bg-[#C44040] dark:bg-[#D96B6B]",
  },
  neutral: {
    label: "Neutro",
    icon: Info,
    bg: "bg-[#F5F5F8] dark:bg-[#1C1C21]",
    border: "border-[#DCDCE8] dark:border-[#2A2A32]",
    text: "text-[#6A6A7A] dark:text-[#9494A2]",
    dot: "bg-[#9090A8] dark:bg-[#7C7C88]",
  },
};
