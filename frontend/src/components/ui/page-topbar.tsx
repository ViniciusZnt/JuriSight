"use client";

import { ChevronRight } from "lucide-react";

interface Crumb {
  label: string;
  onClick?: () => void;
}

interface PageTopbarProps {
  /** Trilha de navegação; o último item é a página atual (não clicável). */
  crumbs: Crumb[];
  bordered?: boolean;
  /** Esconde o primeiro crumb (e o separador seguinte) em telas pequenas. */
  hideFirstOnMobile?: boolean;
}

/** Cabeçalho padrão das telas do fluxo de consulta: breadcrumb. */
export function PageTopbar({ crumbs, bordered = false, hideFirstOnMobile = false }: PageTopbarProps) {
  return (
    <header
      className={`flex items-center justify-between gap-3 pl-20 pr-4 sm:pl-20 sm:pr-8 py-4 bg-[#F7F7F9] dark:bg-[#0E0E11] sticky top-0 z-10 ${
        bordered ? "border-b border-[#EBEBEF] dark:border-[#26262C]" : ""
      }`}
    >
      <div className="flex items-center gap-2 min-w-0 overflow-hidden">
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;
          const hideThisOnMobile = hideFirstOnMobile && idx === 0;
          const hideChevronOnMobile = hideFirstOnMobile && idx === 1;

          return (
            <div key={crumb.label} className="flex items-center gap-2">
              {idx > 0 && (
                <ChevronRight
                  className={`w-3 h-3 text-[#D0D0DA] dark:text-[#3A3A42] ${hideChevronOnMobile ? "hidden sm:block" : ""}`}
                  strokeWidth={2}
                />
              )}
              {isLast ? (
                <span
                  className={`text-[#4A4A5A] dark:text-[#C4C4CE] truncate ${hideThisOnMobile ? "hidden sm:inline" : ""}`}
                  style={{ fontSize: "14.4px", fontWeight: 500 }}
                >
                  {crumb.label}
                </span>
              ) : (
                <button
                  onClick={crumb.onClick}
                  className={`text-[#AEAEBF] dark:text-[#6E6E7C] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-colors truncate ${
                    hideThisOnMobile ? "hidden sm:inline" : ""
                  }`}
                  style={{ fontSize: "14.4px" }}
                >
                  {crumb.label}
                </button>
              )}
            </div>
          );
        })}
      </div>

    </header>
  );
}
