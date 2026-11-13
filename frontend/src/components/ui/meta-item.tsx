import type { LucideIcon } from "lucide-react";

interface MetaItemProps {
  icon: LucideIcon;
  children: React.ReactNode;
  /** Versão menor dos cartões e de Salvos: ícone pequeno e cor e tamanho de letra herdados do pai. */
  compacto?: boolean;
}

/** Linha "ícone + texto" curta usada nos metadados da decisão (tribunal, data, processo…). */
export function MetaItem({ icon: Icon, children, compacto = false }: MetaItemProps) {
  return (
    <div
      className={compacto ? "flex items-center gap-1.5" : "flex items-center gap-2 text-[#6B6B80] dark:text-[#A6A6B4]"}
      style={compacto ? undefined : { fontSize: "13.8px" }}
    >
      <Icon
        className={compacto ? "w-3 h-3 flex-shrink-0" : "w-3.5 h-3.5 flex-shrink-0 text-[#9090A8] dark:text-[#7C7C88]"}
        strokeWidth={1.8}
      />
      {children}
    </div>
  );
}
