"use client";

import { useState } from "react";
import Link from "next/link";
import { TrendingUp, Bookmark, AlertCircle, Scale, Calendar, FileText, ChevronDown, Copy, CheckCircle2 } from "lucide-react";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { outcomeDe, rotuloSelo } from "@/lib/provimento";
import { ProvimentoPanel } from "@/components/provimento/provimento-panel";
import { assuntoDoCard, ementaComCitacao, formatarData, matchedEntities, titleFromEmenta, truncate, TIPO_DOCUMENTO_LABEL } from "@/lib/decision-view";
import { useSaved } from "@/lib/saved";
import { copiarTexto } from "@/lib/utils";
import type { EstruturaArgumentativa, ResultCard } from "@/lib/api";
import { BUSCA } from "@/lib/cores-busca";

interface Props {
  decision: ResultCard;
  estrutura: EstruturaArgumentativa | null;
  /** Posição por relevância na faixa; sem ela (faixa livre) o selo "#N" não aparece. */
  rank?: number;
  total?: number;
  /** Rank do card com a mesma ementa, quando repetida. */
  ementaIgualA?: number;
  /** "decisao" na faixa restrita (âncora das chips da resposta); outro prefixo na livre. */
  idPrefix?: string;
}

/** Card de decisão da tela de resultados, igual nas duas faixas. */
/** "Achada pela semântica e pelos termos" — por onde a decisão entrou, antes da fusão. */
function origemDoCard(canais: ("semantica" | "termos")[]): string {
  const nomes = { semantica: "pela semântica", termos: "pelos termos" };
  return `Achada ${canais.map((c) => nomes[c]).join(" e ")}`;
}

export function ResultadoCard({ decision, estrutura, rank, total, ementaIgualA, idPrefix = "decisao" }: Props) {
  const { isSaved, toggle } = useSaved();
  const [expandida, setExpandida] = useState(false);
  const [copiada, setCopiada] = useState(false);
  const saved = isSaved(decision.id);
  const title = assuntoDoCard(titleFromEmenta(decision.ementa));
  const outcome = outcomeDe(decision);
  const entidades = matchedEntities(estrutura, decision.ementa);

  const toggleSave = () =>
    toggle({
      id: decision.id,
      title: titleFromEmenta(decision.ementa),
      court: decision.tribunal,
      chamber: decision.turma,
      date: decision.data_julgamento ?? "",
      outcome,
      relevance: rank ?? 0,
      rapporteur: decision.relator,
      processNumber: decision.numero_processo,
    });
  const formatDate = (d: string | null) => formatarData(d, "short");

  return (
          // O título é o link (Ctrl+clique, nova aba, Tab); o ::after dele cobre o card inteiro
          // para o clique em qualquer ponto abrir a decisão. Controles internos ficam com z-10.
          <div
            id={`${idPrefix}-${decision.id}`}
            className={`relative scroll-mt-16 target:ring-2 target:ring-[#1A3A5C]/40 dark:target:ring-[#8AB0DC]/50 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_3px_16px_rgba(0,0,0,0.09)] dark:shadow-none dark:hover:border-[#33333C] transition-all overflow-hidden group ${
              rank !== undefined ? "grid grid-cols-[56px_minmax(0,1fr)]" : ""
            }`}
          >
            {/* Posição na busca: a âncora visual do card */}
            {rank !== undefined && (
              <div
                title={`${rank}º mais relevante de ${total} nesta busca`}
                aria-label={`${rank}º mais relevante de ${total} nesta busca`}
                className="flex flex-col items-center gap-0.5 pt-5 bg-[#F5F8FD] dark:bg-[#131C28] border-r border-[#E8EEF7] dark:border-[#26313F]"
              >
                <TrendingUp className="w-3.5 h-3.5 mb-0.5 text-[#9090A8] dark:text-[#7C8AA0]" strokeWidth={1.8} />
                <span className="text-[#1A3A5C] dark:text-[#8AB0DC] tabular-nums" style={{ fontSize: "18px", fontWeight: 700, lineHeight: 1 }}>
                  #{rank}
                </span>
                {total !== undefined && (
                  <span className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "10.5px", fontWeight: 600 }}>
                    de {total}
                  </span>
                )}
              </div>
            )}
            <div className="min-w-0">
            {/* Header */}
            <div className="px-6 pt-5 pb-4 border-b border-[#F0F0F6] dark:border-[#26262C]">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 sm:gap-4 mb-3">
                <h3 className="text-[#0F1117] dark:text-[#ECECEF] leading-snug group-hover:text-[#1A3A5C] dark:group-hover:text-[#8AB0DC] transition-colors flex-1" style={{ fontSize: "16.7px", fontWeight: 600 }}>
                  <Link href={`/decisao/${decision.id}`} className="after:absolute after:inset-0">
                    {title}
                  </Link>
                </h3>
                <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                  <OutcomeBadge outcome={outcome} label={rotuloSelo(decision)} size="sm" />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
                <MetaItem icon={Scale} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                  <span>{[decision.sigla_classe, decision.tribunal].filter(Boolean).join(" · ")} — {decision.turma}</span>
                </MetaItem>
                <MetaItem icon={Calendar} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                  <span>{formatDate(decision.data_julgamento)}</span>
                </MetaItem>
                <MetaItem icon={FileText} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                  <span className="font-mono">{decision.numero_processo}</span>
                </MetaItem>
              </div>
              {decision.canais && decision.canais.length > 0 && (
                <p className="mt-1.5 flex items-center gap-1.5 text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "12.6px" }}>
                  {decision.canais.map((c) => (
                    <span key={c} className={`w-2 h-2 rounded-sm ${c === "semantica" ? BUSCA.semantica.ponto : BUSCA.termos.ponto}`} />
                  ))}
                  {origemDoCard(decision.canais)}
                </p>
              )}
            </div>

            {/* Provimento (Jev) */}
            <div className="relative z-10 px-6 py-3 border-b border-[#F0F0F6] dark:border-[#26262C]">
              <ProvimentoPanel compacto documentoId={decision.id} provimento={decision.provimento} classificacao={decision.classificacao_provimento} />
            </div>

            {/* Summary */}
            <div className="px-6 py-4">
              <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 whitespace-pre-line" style={{ fontSize: "14.4px" }}>
                {expandida ? decision.ementa.trim() : truncate(decision.ementa, 400)}
              </p>
              {decision.ementa.trim().length > 400 && (
                <button
                  onClick={() => setExpandida((v) => !v)}
                  aria-expanded={expandida}
                  className="relative z-10 flex items-center gap-1 -mt-1 mb-3 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
                  style={{ fontSize: "13.2px", fontWeight: 500 }}
                >
                  {expandida ? "Recolher ementa" : "Ver ementa completa"}
                  <ChevronDown className={`w-3 h-3 transition-transform ${expandida ? "rotate-180" : ""}`} strokeWidth={2} />
                </button>
              )}

              {entidades.length > 0 && (
                <div className="flex items-start gap-2 mb-3">
                  <AlertCircle className="w-3 h-3 text-[#9090A8] dark:text-[#7C7C88] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
                  <div className="flex flex-wrap gap-1.5 items-center">
                    <span className="text-[#9090A8] dark:text-[#7C7C88]" style={{ fontSize: "12.6px" }}>Entidades correspondentes:</span>
                    {entidades.map((entity, idx) => (
                      <Chip key={idx} tone="amber" size="sm">
                        {entity}
                      </Chip>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-1.5">
                <Chip tone="blue" size="sm">
                  {TIPO_DOCUMENTO_LABEL[decision.tipo_documento]}
                </Chip>
                {ementaIgualA !== undefined && (
                  <Chip tone="amber" size="sm">
                    Ementa igual à de #{ementaIgualA}
                  </Chip>
                )}
              </div>
            </div>

            {/* Footer actions */}
            <div className="px-6 py-3 bg-[#FAFAFA] dark:bg-[#1C1C21] border-t border-[#F0F0F6] dark:border-[#26262C] flex flex-wrap items-center justify-between gap-2">
              <span className="text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.6px" }}>
                Rel. {decision.relator}
              </span>
              <div className="flex items-center gap-2">
                <ActionButton
                  icon={copiada ? CheckCircle2 : Copy}
                  label={copiada ? "Copiada!" : "Copiar ementa"}
                  tone={copiada ? "success" : "neutral"}
                  size="sm"
                  className="relative z-10"
                  title="Copiar a ementa com a linha de citação (tribunal, turma, processo, data, relator)"
                  onClick={() =>
                    copiarTexto(ementaComCitacao(decision)).then(() => {
                      setCopiada(true);
                      setTimeout(() => setCopiada(false), 2000);
                    })
                  }
                />
                <ActionButton
                  icon={Bookmark}
                  label={saved ? "Salvo" : "Salvar"}
                  tone={saved ? "accent" : "neutral"}
                  size="sm"
                  iconFill={saved}
                  className="relative z-10"
                  onClick={() => toggleSave()}
                />
              </div>
            </div>
            </div>
          </div>
  );
}
