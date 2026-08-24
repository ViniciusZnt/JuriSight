"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Filter,
  TrendingUp,
  ArrowUpDown,
  Bookmark,
  AlertCircle,
  Scale,
  Calendar,
  FileText,
  Search,
} from "lucide-react";
import { StepIndicator } from "@/components/step-indicator";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import type { Outcome } from "@/lib/outcome";

interface Decision {
  id: string;
  title: string;
  court: string;
  chamber: string;
  date: string;
  outcome: Outcome;
  relevance: number;
  rapporteur: string;
  processNumber: string;
  summary: string;
  tags: string[];
  matchedEntities: string[];
}

const mockResults: Decision[] = [
  {
    id: "1",
    title: "Adicional de insalubridade — exposição a agentes químicos cancerígenos",
    court: "TST",
    chamber: "3ª Turma",
    date: "2025-04-28",
    outcome: "favorable",
    relevance: 98,
    rapporteur: "Min. Alberto Bresciani",
    processNumber: "TST-RR-100-44.2021.5.01.0019",
    summary:
      "Mantida condenação ao pagamento de adicional de insalubridade em grau máximo ante a comprovação de exposição habitual e permanente a benzeno. Empresa tinha ciência do risco e não forneceu EPI eficaz. Laudo pericial confirmou a presença do agente nocivo acima dos limites de tolerância.",
    tags: ["NR-15", "CLT 192", "Benzeno", "Insalubridade grau máximo"],
    matchedEntities: ["Benzeno", "NR-15", "Ausência de EPI eficaz"],
  },
  {
    id: "2",
    title: "Responsabilidade patronal por exposição a agente insalubre sem monitoramento",
    court: "TRT-2",
    chamber: "14ª Turma",
    date: "2025-04-15",
    outcome: "favorable",
    relevance: 95,
    rapporteur: "Des. Carlos Roberto Barbosa",
    processNumber: "TRT2-ROT-1000523-31.2024.5.02.0066",
    summary:
      "Reconhecida a responsabilidade da empregadora pelo não fornecimento de proteção adequada e pela ausência de monitoramento de saúde ocupacional. Aplicação da Súmula 448 do TST. Trabalhador exposto a hidrocarbonetos aromáticos sem controle médico.",
    tags: ["Súmula 448 TST", "Monitoramento", "Hidrocarbonetos"],
    matchedEntities: ["Hidrocarbonetos aromáticos", "Exposição contínua sem monitoramento"],
  },
  {
    id: "3",
    title: "Uso de EPI como fator excludente do adicional de insalubridade",
    court: "TRT-15",
    chamber: "5ª Turma",
    date: "2025-03-22",
    outcome: "unfavorable",
    relevance: 82,
    rapporteur: "Des. Lorival Ferreira dos Santos",
    processNumber: "TRT15-ROT-0010234-19.2024.5.15.0089",
    summary:
      "Afastado o adicional de insalubridade ante a comprovação do fornecimento e uso efetivo de EPI adequado, capaz de neutralizar o agente nocivo. Perícia constatou o uso correto e a eficácia dos equipamentos fornecidos pela empresa.",
    tags: ["EPI", "Súmula 289 TST", "Neutralização"],
    matchedEntities: ["Ausência de EPI eficaz"],
  },
  {
    id: "4",
    title: "Insalubridade — necessidade de laudo técnico contemporâneo aos fatos",
    court: "TST",
    chamber: "8ª Turma",
    date: "2025-03-10",
    outcome: "neutral",
    relevance: 78,
    rapporteur: "Min. Dora Maria da Costa",
    processNumber: "TST-AIRR-20700-73.2023.5.04.0303",
    summary:
      "Indeferido pedido de adicional de insalubridade por ausência de prova técnica contemporânea aos fatos. Laudo pericial realizado após a rescisão contratual não se presta a demonstrar as condições de trabalho durante o período laborado.",
    tags: ["Laudo pericial", "Prova técnica", "CLT 195"],
    matchedEntities: ["NR-15"],
  },
  {
    id: "5",
    title: "Ciência patronal do risco e responsabilidade civil objetiva",
    court: "TRT-1",
    chamber: "7ª Turma",
    date: "2025-02-18",
    outcome: "favorable",
    relevance: 91,
    rapporteur: "Des. Ana Paula Tauceda Branco",
    processNumber: "TRT1-RO-0101234-56.2024.5.01.0048",
    summary:
      "Empresa tinha pleno conhecimento dos riscos à saúde do trabalhador, conforme documentação interna apresentada (PPP, PPRA, PCMSO). Caracterizada negligência no fornecimento de proteção adequada. Condenação em adicional de insalubridade e danos morais.",
    tags: ["Ciência patronal", "Dano moral", "Responsabilidade objetiva"],
    matchedEntities: ["Empresa ciente", "Falta de treinamento"],
  },
];

/** Resultados da busca (Figuras 4-5 da RFC). Dados mockados até a API existir. */
export function SearchResultsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<"all" | Outcome>("all");
  const [sortBy, setSortBy] = useState<"relevance" | "date">("relevance");
  const [savedItems, setSavedItems] = useState<Set<string>>(new Set());

  const filteredResults = mockResults
    .filter((d) => filter === "all" || d.outcome === filter)
    .sort((a, b) => (sortBy === "relevance" ? b.relevance - a.relevance : new Date(b.date).getTime() - new Date(a.date).getTime()));

  const toggleSave = (id: string) => {
    setSavedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });

  const favorableCount = mockResults.filter((d) => d.outcome === "favorable").length;
  const unfavorableCount = mockResults.filter((d) => d.outcome === "unfavorable").length;

  return (
    <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <PageTopbar
        queriesLeft={46}
        crumbs={[
          { label: "Início", onClick: () => router.push("/") },
          { label: "Revisão", onClick: () => router.push("/revisao") },
          { label: "Jurisprudências" },
        ]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-8 py-4 pb-10">
        <StepIndicator current={2} />

        {/* Summary banner */}
        <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none px-6 py-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex-shrink-0">
              <Scale className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
            </div>
            <div>
              <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "16.7px", fontWeight: 600 }}>
                {filteredResults.length} decisões encontradas
              </h2>
              <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
                Alinhadas à tese: &ldquo;Adicional de insalubridade grau máximo&rdquo;
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#EDF7F2] dark:bg-[#122A1E] border border-[#BDE0CF] dark:border-[#1E4A34]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#2D8A5F] dark:bg-[#3DA372]" />
              <span className="text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                {favorableCount} favoráveis
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#FBF0F0] dark:bg-[#2A1517] border border-[#E8C2C2] dark:border-[#4A2529]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#C44040] dark:bg-[#D96B6B]" />
              <span className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                {unfavorableCount} desfavorável{unfavorableCount === 1 ? "" : "eis"}
              </span>
            </div>
          </div>
        </div>

        {/* Filters and sort */}
        <div className="w-full max-w-[800px] flex flex-wrap items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-[#9090A8] dark:text-[#7C7C88]" strokeWidth={1.8} />
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filter === "all"
                  ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(26,58,92,0.24)]"
                  : "bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30"
              }`}
              style={{ fontSize: "13.8px", fontWeight: filter === "all" ? 600 : 400 }}
            >
              Todas ({mockResults.length})
            </button>
            <button
              onClick={() => setFilter("favorable")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filter === "favorable"
                  ? "bg-[#2D8A5F] dark:bg-[#3DA372] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(45,138,95,0.24)]"
                  : "bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#2D8A5F]/30 dark:hover:border-[#3DA372]/30"
              }`}
              style={{ fontSize: "13.8px", fontWeight: filter === "favorable" ? 600 : 400 }}
            >
              Favoráveis ({favorableCount})
            </button>
            <button
              onClick={() => setFilter("unfavorable")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                filter === "unfavorable"
                  ? "bg-[#C44040] dark:bg-[#D96B6B] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(196,64,64,0.24)]"
                  : "bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#C44040]/30 dark:hover:border-[#D96B6B]/30"
              }`}
              style={{ fontSize: "13.8px", fontWeight: filter === "unfavorable" ? 600 : 400 }}
            >
              Desfavoráveis ({unfavorableCount})
            </button>
          </div>

          <button
            onClick={() => setSortBy(sortBy === "relevance" ? "date" : "relevance")}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white dark:bg-[#17171B] border border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30 transition-all"
            style={{ fontSize: "13.8px" }}
          >
            <ArrowUpDown className="w-3.5 h-3.5" strokeWidth={1.8} />
            {sortBy === "relevance" ? "Relevância" : "Data"}
          </button>
        </div>

        {/* Results list */}
        {filteredResults.length === 0 ? (
          <div className="w-full max-w-[800px] flex flex-col items-center justify-center py-20 text-center">
            <div className="w-12 h-12 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex items-center justify-center mb-4">
              <Search className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
            </div>
            <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "17.8px", fontWeight: 600 }}>
              Nenhuma decisão neste filtro
            </h2>
            <p className="mt-2 max-w-sm text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.9px" }}>
              Tente outro filtro de resultado para ver as demais decisões encontradas.
            </p>
          </div>
        ) : (
          <div className="w-full max-w-[800px] space-y-4">
            {filteredResults.map((decision) => {
              const isSaved = savedItems.has(decision.id);

              return (
                <div
                  key={decision.id}
                  className="bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_3px_16px_rgba(0,0,0,0.09)] dark:shadow-none dark:hover:border-[#33333C] transition-all overflow-hidden group cursor-pointer"
                  onClick={() => router.push(`/decisao/${decision.id}`)}
                >
                  {/* Header */}
                  <div className="px-6 pt-5 pb-4 border-b border-[#F0F0F6] dark:border-[#26262C]">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <h3 className="text-[#0F1117] dark:text-[#ECECEF] leading-snug group-hover:text-[#1A3A5C] dark:group-hover:text-[#8AB0DC] transition-colors flex-1" style={{ fontSize: "16.7px", fontWeight: 600 }}>
                        {decision.title}
                      </h3>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <OutcomeBadge outcome={decision.outcome} size="sm" />
                        <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]">
                          <TrendingUp className="w-3 h-3 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                          <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                            {decision.relevance}%
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
                      <MetaItem icon={Scale} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span>{decision.court} — {decision.chamber}</span>
                      </MetaItem>
                      <MetaItem icon={Calendar} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span>{formatDate(decision.date)}</span>
                      </MetaItem>
                      <MetaItem icon={FileText} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span className="font-mono">{decision.processNumber}</span>
                      </MetaItem>
                    </div>
                  </div>

                  {/* Summary */}
                  <div className="px-6 py-4">
                    <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3" style={{ fontSize: "14.4px" }}>
                      {decision.summary}
                    </p>

                    {decision.matchedEntities.length > 0 && (
                      <div className="flex items-start gap-2 mb-3">
                        <AlertCircle className="w-3 h-3 text-[#9090A8] dark:text-[#7C7C88] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
                        <div className="flex flex-wrap gap-1.5 items-center">
                          <span className="text-[#9090A8] dark:text-[#7C7C88]" style={{ fontSize: "12.6px" }}>Entidades correspondentes:</span>
                          {decision.matchedEntities.map((entity, idx) => (
                            <Chip key={idx} tone="amber" size="sm">
                              {entity}
                            </Chip>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-1.5">
                      {decision.tags.map((tag, idx) => (
                        <Chip key={idx} tone="blue" size="sm">
                          {tag}
                        </Chip>
                      ))}
                    </div>
                  </div>

                  {/* Footer actions */}
                  <div className="px-6 py-3 bg-[#FAFAFA] dark:bg-[#1C1C21] border-t border-[#F0F0F6] dark:border-[#26262C] flex items-center justify-between">
                    <span className="text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "12.6px" }}>
                      Rel. {decision.rapporteur}
                    </span>
                    <ActionButton
                      icon={Bookmark}
                      label={isSaved ? "Salvo" : "Salvar"}
                      tone={isSaved ? "accent" : "neutral"}
                      size="sm"
                      iconFill={isSaved}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSave(decision.id);
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
