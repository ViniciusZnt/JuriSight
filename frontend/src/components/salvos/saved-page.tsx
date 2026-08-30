"use client";

import { useRouter } from "next/navigation";
import { Bookmark, Scale, Calendar, FileText, X } from "lucide-react";
import { MetaItem } from "@/components/ui/meta-item";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { useSaved } from "@/lib/saved";

/** Salvos — decisões marcadas pelo usuário (botão "Salvar" nos resultados e no detalhe do acórdão). */
export function SavedPage() {
  const router = useRouter();
  const { saved, toggle } = useSaved();

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });

  return (
    <div className="min-h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <header className="pl-20 pr-8 py-4">
        <h1 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "20.7px", fontWeight: 600 }}>
          Salvos
        </h1>
      </header>

      {saved.length === 0 ? (
        <div className="flex flex-col items-center justify-center px-8 py-24 text-center">
          <div className="w-12 h-12 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex items-center justify-center mb-4">
            <Bookmark className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
          </div>
          <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "17.2px", fontWeight: 600 }}>
            Nenhuma decisão salva ainda
          </h2>
          <p className="mt-2 max-w-sm text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.9px" }}>
            Ao abrir um acórdão, use <span className="text-[#1A3A5C] dark:text-[#8AB0DC]">Salvar</span> para guardá-lo aqui e
            consultar depois.
          </p>
        </div>
      ) : (
        <div className="px-4 sm:px-8 pb-10">
          <div className="max-w-[800px] mx-auto space-y-3">
            {saved.map((d) => (
              <div
                key={d.id}
                onClick={() => router.push(`/decisao/${d.id}`)}
                className="group flex items-start justify-between gap-4 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_3px_16px_rgba(0,0,0,0.09)] dark:shadow-none dark:hover:border-[#33333C] transition-all px-5 py-4 cursor-pointer"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <OutcomeBadge outcome={d.outcome} size="sm" />
                  </div>
                  <h3
                    className="text-[#0F1117] dark:text-[#ECECEF] leading-snug group-hover:text-[#1A3A5C] dark:group-hover:text-[#8AB0DC] transition-colors mb-1.5"
                    style={{ fontSize: "15.5px", fontWeight: 600 }}
                  >
                    {d.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
                    <MetaItem icon={Scale} className="" iconClassName="" iconSize="w-3 h-3" fontSize="12.6px" gap="gap-1.5">
                      <span>{d.court} — {d.chamber}</span>
                    </MetaItem>
                    <MetaItem icon={Calendar} className="" iconClassName="" iconSize="w-3 h-3" fontSize="12.6px" gap="gap-1.5">
                      <span>{formatDate(d.date)}</span>
                    </MetaItem>
                    <MetaItem icon={FileText} className="" iconClassName="" iconSize="w-3 h-3" fontSize="12.6px" gap="gap-1.5">
                      <span className="font-mono">{d.processNumber}</span>
                    </MetaItem>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(d);
                  }}
                  title="Remover dos salvos"
                  className="flex items-center justify-center w-7 h-7 rounded-lg text-[#AEAEBF] dark:text-[#6E6E7C] hover:bg-[#FBF0F0] hover:text-[#C44040] dark:hover:bg-[#2A1517] dark:hover:text-[#D96B6B] transition-colors flex-shrink-0"
                >
                  <X className="w-3.5 h-3.5" strokeWidth={2} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
