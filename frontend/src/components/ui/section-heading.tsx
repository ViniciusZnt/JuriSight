import type { LucideIcon } from "lucide-react";

interface SectionHeadingProps {
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  title: string;
}

/** Ícone em caixa + título, usado no cabeçalho de cada seção do detalhe da decisão. */
export function SectionHeading({ icon: Icon, iconBg, iconColor, title }: SectionHeadingProps) {
  return (
    <div className="flex items-center gap-2.5">
      <div className={`flex items-center justify-center w-7 h-7 rounded-lg ${iconBg}`}>
        <Icon className={`w-3.5 h-3.5 ${iconColor}`} strokeWidth={1.8} />
      </div>
      <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "16.1px", fontWeight: 600 }}>
        {title}
      </h2>
    </div>
  );
}
