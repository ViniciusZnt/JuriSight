"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bookmark,
  Share2,
  Copy,
  ExternalLink,
  Scale,
  Calendar,
  MapPin,
  FileText,
  User,
  CheckCircle2,
  AlertCircle,
  Quote,
  BookOpen,
  Gavel,
  TrendingUp,
  SlidersHorizontal,
  Loader2,
  FileX,
} from "lucide-react";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { SectionHeading } from "@/components/ui/section-heading";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { provimentoToOutcome } from "@/lib/outcome";
import { matchedEntities, relevancePercent, titleFromEmenta, TIPO_DOCUMENTO_LABEL } from "@/lib/decision-view";
import { useSaved } from "@/lib/saved";
import { useSearchSession } from "@/lib/search-session";
import { getDocument, ApiError, type DocumentoDetalhe } from "@/lib/api";

/** Detalhe do acórdão (Figuras 6-7 da RFC). Busca o DocumentoJuridico completo via GET
 *  /document/{id}; a relevância (score_rrf) e a EstruturaArgumentativa pesquisada vêm do
 *  SearchSession quando disponíveis (ex.: chegou aqui pela lista de resultados) — abrir o link
 *  direto (ex.: em Salvos) ainda funciona, só sem esses dois complementos. */
export function DecisionDetailPage({ decisionId }: { decisionId: string }) {
  const router = useRouter();
  const { isSaved: isSavedCtx, toggle } = useSaved();
  const { estrutura, resultados } = useSearchSession();
  const [doc, setDoc] = useState<DocumentoDetalhe | null>(null);
  const [error, setError] = useState<{ notFound: boolean; message: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["summary", "matches", "grounds", "decision"])
  );

  useEffect(() => {
    let cancelled = false;
    setDoc(null);
    setError(null);
    getDocument(decisionId)
      .then((res) => {
        if (!cancelled) setDoc(res);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const notFound = err instanceof ApiError && err.status === 404;
        setError({
          notFound,
          message: notFound
            ? "Documento não encontrado."
            : err instanceof ApiError
              ? err.message
              : "Não foi possível carregar esta decisão agora.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [decisionId]);

  const formatDate = (dateStr: string | null) =>
    dateStr ? new Date(dateStr).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" }) : "Data não informada";

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const copyText = async (text: string, onDone: () => void) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* clipboard indisponível */
      }
      document.body.removeChild(ta);
    }
    onDone();
  };

  if (error) {
    return (
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
        <PageTopbar bordered queriesLeft={46} crumbs={[{ label: "Início", onClick: () => router.push("/resultados") }, { label: "Decisão" }]} />
        <div className="flex-1 flex flex-col items-center justify-center px-8 py-20 text-center">
          <div className="w-12 h-12 rounded-xl bg-[#FBF0F0] dark:bg-[#2A1517] flex items-center justify-center mb-4">
            <FileX className="w-5 h-5 text-[#C44040] dark:text-[#D96B6B]" strokeWidth={1.8} />
          </div>
          <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "17.8px", fontWeight: 600 }}>
            {error.notFound ? "Documento não encontrado" : "Não foi possível carregar a decisão"}
          </h2>
          <p className="mt-2 max-w-sm text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.9px" }}>
            {error.message}
          </p>
          <button
            onClick={() => router.push("/resultados")}
            className="flex items-center gap-1.5 px-3.5 py-2 mt-5 rounded-lg bg-[#1A3A5C] text-white hover:bg-[#1E4570] transition-colors"
            style={{ fontSize: "13.8px", fontWeight: 600 }}
          >
            <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.8} />
            Voltar aos resultados
          </button>
        </div>
      </main>
    );
  }

  if (!doc) {
    return (
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
        <PageTopbar bordered queriesLeft={46} crumbs={[{ label: "Início", onClick: () => router.push("/resultados") }, { label: "Decisão" }]} />
        <div className="flex-1 flex flex-col items-center justify-center py-24">
          <Loader2 className="w-6 h-6 text-[#1A3A5C] dark:text-[#8AB0DC] animate-spin" strokeWidth={2} />
          <p className="mt-3 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px" }}>Carregando decisão…</p>
        </div>
      </main>
    );
  }

  const title = titleFromEmenta(doc.ementa);
  const outcome = provimentoToOutcome(doc.provimento);
  const origin = doc.gabinete || doc.tribunal;
  const entidades = matchedEntities(estrutura, `${doc.ementa} ${doc.fundamentacao} ${doc.acordao}`);
  const fromResults = resultados?.find((r) => r.id === doc.id);
  const maxScore = resultados?.reduce((max, r) => Math.max(max, r.score_rrf), 0) ?? 0;
  const relevance = fromResults ? relevancePercent(fromResults.score_rrf, maxScore) : null;

  const buildFullDocument = () => {
    const lines: string[] = [];
    lines.push(title, "");
    lines.push(`${doc.tribunal} — ${doc.turma}`);
    lines.push(`Data: ${formatDate(doc.data_julgamento)}`);
    lines.push(`Processo: ${doc.numero_processo}`);
    lines.push(`Relator: ${doc.relator}`);
    lines.push(`Origem: ${origin}`);
    if (relevance !== null) lines.push(`Relevância: ${relevance}%`);
    lines.push("");
    if (entidades.length) {
      lines.push("ENTIDADES CORRESPONDENTES");
      lines.push(entidades.map((e) => `• ${e}`).join("\n"), "");
    }
    lines.push("EMENTA", doc.ementa, "");
    if (doc.relatorio) lines.push("RELATÓRIO", doc.relatorio, "");
    if (doc.fundamentacao) lines.push("FUNDAMENTAÇÃO", doc.fundamentacao, "");
    if (doc.acordao) lines.push("DISPOSITIVO", doc.acordao, "");
    if (doc.votos) lines.push("VOTOS", doc.votos, "");
    if (doc.referencia_legislativa.length) {
      lines.push("DISPOSITIVOS LEGAIS CITADOS", doc.referencia_legislativa.map((r) => `• ${r}`).join("\n"), "");
    }
    if (doc.link_original) lines.push(`Fonte: ${doc.link_original}`);
    return lines.join("\n");
  };

  return (
    <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <PageTopbar
        bordered
        queriesLeft={46}
        crumbs={[
          { label: "Início", onClick: () => router.push("/resultados") },
          { label: "Jurisprudências", onClick: () => router.push("/resultados") },
          { label: "Decisão" },
        ]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-8 py-6 pb-10">
        <div className="w-full max-w-[800px] mb-4">
          <button
            onClick={() => router.push("/resultados")}
            className="flex items-center gap-2 text-[#9090A8] dark:text-[#7C7C88] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-colors"
            style={{ fontSize: "14.9px" }}
          >
            <ArrowLeft className="w-3.5 h-3.5" strokeWidth={2} />
            Voltar aos resultados
          </button>
        </div>

        <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none overflow-hidden">
          {/* Header */}
          <div className="px-5 sm:px-7 pt-6 pb-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="flex items-start justify-between gap-4 mb-4">
              <h1 className="text-[#0F1117] dark:text-[#ECECEF] leading-tight flex-1" style={{ fontSize: "20.7px", fontWeight: 600 }}>
                {title}
              </h1>
              <div className="flex items-center gap-2 flex-shrink-0">
                <OutcomeBadge outcome={outcome} size="md" suffix=" à tese" />
                {relevance !== null && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]">
                    <TrendingUp className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                    <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                      {relevance}% relevância
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 mb-4">
              <MetaItem icon={Scale}>
                <span className="font-medium text-[#4A4A5A] dark:text-[#C4C4CE]">{doc.tribunal}</span>
                <span>—</span>
                <span>{doc.turma}</span>
              </MetaItem>
              <MetaItem icon={Calendar}>
                <span>{formatDate(doc.data_julgamento)}</span>
              </MetaItem>
              <MetaItem icon={FileText}>
                <span className="font-mono text-[#4A4A5A] dark:text-[#C4C4CE]">{doc.numero_processo}</span>
                <button
                  onClick={() => copyText(doc.numero_processo, () => {})}
                  className="ml-1 hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC]"
                  title="Copiar número do processo"
                >
                  <Copy className="w-3 h-3" strokeWidth={1.8} />
                </button>
              </MetaItem>
              <MetaItem icon={User}>
                <span>Rel. {doc.relator || "Não informado"}</span>
              </MetaItem>
              <MetaItem icon={MapPin}>
                <span>Origem: {origin || "Não informada"}</span>
              </MetaItem>
            </div>

            {/* Actions bar */}
            <div className="flex items-center gap-2 pt-3 border-t border-[#F0F0F6] dark:border-[#26262C] flex-wrap">
              <ActionButton
                icon={Bookmark}
                label={isSavedCtx(doc.id) ? "Salvo" : "Salvar"}
                tone={isSavedCtx(doc.id) ? "accent" : "neutral"}
                iconFill={isSavedCtx(doc.id)}
                onClick={() =>
                  toggle({
                    id: doc.id,
                    title,
                    court: doc.tribunal,
                    chamber: doc.turma,
                    date: doc.data_julgamento ?? "",
                    outcome,
                    relevance: relevance ?? 0,
                    rapporteur: doc.relator,
                    processNumber: doc.numero_processo,
                  })
                }
              />
              <ActionButton
                icon={linkCopied ? CheckCircle2 : Share2}
                label={linkCopied ? "Link copiado!" : "Compartilhar"}
                tone={linkCopied ? "success" : "neutral"}
                onClick={() => copyText(window.location.href, () => { setLinkCopied(true); setTimeout(() => setLinkCopied(false), 2000); })}
                title="Copiar link desta decisão"
              />
              <ActionButton
                icon={copied ? CheckCircle2 : Copy}
                label={copied ? "Copiado!" : "Copiar documento"}
                tone={copied ? "success" : "neutral"}
                onClick={() => copyText(buildFullDocument(), () => { setCopied(true); setTimeout(() => setCopied(false), 2000); })}
                title="Copiar documento completo para a área de transferência"
              />
              <ActionButton
                icon={SlidersHorizontal}
                label="Refinar consulta"
                onClick={() => router.push("/revisao")}
              />
              {doc.link_original && (
                <a href={doc.link_original} target="_blank" rel="noopener noreferrer" className="ml-auto">
                  <ActionButton icon={ExternalLink} label="Ver no site oficial" />
                </a>
              )}
            </div>
          </div>

          {/* Matched entities */}
          {entidades.length > 0 && (
            <div className="px-5 sm:px-7 py-4 bg-[#FAFBFF] dark:bg-[#15191F] border-b border-[#F0F0F6] dark:border-[#26262C]">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
                <div className="flex-1">
                  <span className="text-[#4A4A5A] dark:text-[#C4C4CE] block mb-2" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                    Entidades correspondentes ao seu contexto:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {entidades.map((entity, idx) => (
                      <Chip key={idx} tone="amber" icon={CheckCircle2}>
                        {entity}
                      </Chip>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Summary */}
          <CollapsibleSection
            icon={Quote}
            iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]"
            iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]"
            title="Ementa"
            expanded={expandedSections.has("summary")}
            onToggle={() => toggleSection("summary")}
          >
            <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed" style={{ fontSize: "14.9px", textAlign: "justify" }}>
              {doc.ementa || "Ementa não disponível para este documento."}
            </p>
          </CollapsibleSection>

          {/* Relatório (opcional — nem todo documento tem esta seção preenchida) */}
          {doc.relatorio && (
            <CollapsibleSection
              icon={FileText}
              iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]"
              iconColor="text-[#6A6A7A] dark:text-[#9494A2]"
              title="Relatório"
              expanded={expandedSections.has("relatorio")}
              onToggle={() => toggleSection("relatorio")}
            >
              {doc.relatorio.split("\n\n").map((paragraph, idx) => (
                <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                  {paragraph}
                </p>
              ))}
            </CollapsibleSection>
          )}

          {/* Correspondência com o contexto pesquisado */}
          <section className="px-5 sm:px-7 py-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="mb-3">
              <SectionHeading icon={Gavel} iconBg="bg-[#EDF7F2] dark:bg-[#122A1E]" iconColor="text-[#1E6B4A] dark:text-[#6FCB9A]" title="Correspondência com seu contexto" />
            </div>
            {entidades.length > 0 ? (
              <ul className="space-y-2">
                {entidades.map((point, idx) => (
                  <li key={idx} className="flex items-start gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#2D8A5F] dark:bg-[#3DA372] mt-1.5 flex-shrink-0" />
                    <span className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "14.4px" }}>
                      Termo do seu contexto encontrado no documento: <strong>{point}</strong>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
                {estrutura
                  ? "Nenhum termo do seu contexto (normas, agentes nocivos ou violações) aparece literalmente neste documento."
                  : "Sem uma consulta ativa nesta sessão para comparar com este documento."}
              </p>
            )}
          </section>

          {/* Fundamentação */}
          <CollapsibleSection
            icon={BookOpen}
            iconBg="bg-[#FBF4EC] dark:bg-[#2A2015]"
            iconColor="text-[#7A4A1A] dark:text-[#E0AC6C]"
            title="Fundamentação"
            expanded={expandedSections.has("grounds")}
            onToggle={() => toggleSection("grounds")}
          >
            <div className="prose-sm max-w-none">
              {doc.fundamentacao ? (
                doc.fundamentacao.split("\n\n").map((paragraph, idx) => (
                  <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                    {paragraph}
                  </p>
                ))
              ) : (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px" }}>
                  Fundamentação não disponível para este documento.
                </p>
              )}
            </div>
          </CollapsibleSection>

          {/* Decision */}
          <CollapsibleSection
            icon={Scale}
            iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]"
            iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]"
            title="Dispositivo"
            expanded={expandedSections.has("decision")}
            onToggle={() => toggleSection("decision")}
          >
            <div className="bg-[#FAFAFA] dark:bg-[#1C1C21] rounded-xl p-4 border border-[#EBEBF2] dark:border-[#26262C]">
              {doc.acordao ? (
                doc.acordao.split("\n\n").map((paragraph, idx) => (
                  <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                    {paragraph}
                  </p>
                ))
              ) : (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px" }}>
                  Dispositivo não disponível para este documento.
                </p>
              )}
            </div>
          </CollapsibleSection>

          {/* Votos (opcional) */}
          {doc.votos && (
            <CollapsibleSection
              icon={User}
              iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]"
              iconColor="text-[#6A6A7A] dark:text-[#9494A2]"
              title="Votos"
              expanded={expandedSections.has("votos")}
              onToggle={() => toggleSection("votos")}
            >
              {doc.votos.split("\n\n").map((paragraph, idx) => (
                <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                  {paragraph}
                </p>
              ))}
            </CollapsibleSection>
          )}

          {/* Dispositivos legais citados */}
          {doc.referencia_legislativa.length > 0 && (
            <section className="px-5 sm:px-7 py-5">
              <div className="mb-4">
                <SectionHeading icon={FileText} iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]" iconColor="text-[#6A6A7A] dark:text-[#9494A2]" title="Dispositivos legais citados" />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {doc.referencia_legislativa.map((ref, idx) => (
                  <Chip key={idx} tone="neutral">
                    {ref}
                  </Chip>
                ))}
              </div>
            </section>
          )}

          {/* Tags */}
          <div className="px-5 sm:px-7 py-4 bg-[#FAFAFA] dark:bg-[#1C1C21] border-t border-[#F0F0F6] dark:border-[#26262C]">
            <div className="flex items-center gap-2">
              <Chip tone="blue">{TIPO_DOCUMENTO_LABEL[doc.tipo_documento]}</Chip>
              <Chip tone="neutral">{doc.provimento.replace(/_/g, " ")}</Chip>
            </div>
          </div>
        </div>

        <p className="text-[#C8C8D4] dark:text-[#5E5E6A] mt-5" style={{ fontSize: "12.6px" }}>
          Clique nas seções para expandir ou recolher • Decisão indexada em tempo real
        </p>
      </div>
    </main>
  );
}
