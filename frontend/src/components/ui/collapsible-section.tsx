"use client";

import { ChevronDown, ChevronUp, type LucideIcon } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";

interface CollapsibleSectionProps {
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

/** Seção com título recolhível (usada em Resumo, Fundamentação e Dispositivo do detalhe da decisão). */
export function CollapsibleSection({ icon, iconBg, iconColor, title, expanded, onToggle, children }: CollapsibleSectionProps) {
  return (
    <section className="px-5 sm:px-7 py-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
      <button onClick={onToggle} className="flex items-center justify-between w-full mb-3 group">
        <SectionHeading icon={icon} iconBg={iconBg} iconColor={iconColor} title={title} />
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-[#9090A8] dark:text-[#7C7C88] group-hover:text-[#1A3A5C] dark:group-hover:text-[#8AB0DC]" strokeWidth={2} />
        ) : (
          <ChevronDown className="w-4 h-4 text-[#9090A8] dark:text-[#7C7C88] group-hover:text-[#1A3A5C] dark:group-hover:text-[#8AB0DC]" strokeWidth={2} />
        )}
      </button>
      {expanded && children}
    </section>
  );
}
