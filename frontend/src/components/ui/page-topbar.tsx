"use client";

import { ChevronRight, Star, Zap } from "lucide-react";

interface Crumb {
  label: string;
  onClick?: () => void;
}

interface PageTopbarProps {
  /** Trilha de navegação; o último item é a página atual (não clicável). */
  crumbs: Crumb[];
  queriesLeft: number;
  bordered?: boolean;
  /** Esconde o primeiro crumb (e o separador seguinte) em telas pequenas. */
  hideFirstOnMobile?: boolean;
}

/** Cabeçalho padrão das telas do fluxo de consulta: breadcrumb + badges de plano/consultas. */
export function PageTopbar({ crumbs, queriesLeft, bordered = false, hideFirstOnMobile = false }: PageTopbarProps) {
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

      <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
          <Star className="w-3 h-3 text-[#C19A2E]" strokeWidth={2} fill="currentColor" />
          <span className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
            Plano Pro
          </span>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-full bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
          <Zap className="w-3 h-3 text-[#1A3A5C] dark:text-[#8AB0DC] flex-shrink-0" strokeWidth={2} />
          <span className="text-[#4A4A5A] dark:text-[#C4C4CE] whitespace-nowrap" style={{ fontSize: "13.2px", fontWeight: 500 }}>
            <span className="sm:hidden">{queriesLeft}</span>
            <span className="hidden sm:inline">{queriesLeft} consultas restantes</span>
          </span>
        </div>
      </div>
    </header>
  );
}
