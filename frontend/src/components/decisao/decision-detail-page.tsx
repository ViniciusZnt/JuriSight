"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bookmark,
  Share2,
  Download,
  Copy,
  ExternalLink,
  Scale,
  Calendar,
  MapPin,
  FileText,
  User,
  CheckCircle2,
  Quote,
  BookOpen,
  Gavel,
  SlidersHorizontal,
  Loader2,
} from "lucide-react";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { SectionHeading } from "@/components/ui/section-heading";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ErrorBanner } from "@/components/ui/error-banner";
import { getDocument, ApiError, type DocumentoDetalhe, type TipoDocumento } from "@/lib/api";
import { provimentoToOutcome } from "@/lib/outcome";
import { useSaved } from "@/lib/saved";

const TIPO_LABEL: Record<TipoDocumento, string> = {
  ACORDAO: "Acórdão",
  SUMULA: "Súmula",
  OJ: "Orientação Jurisprudencial",
  PRECEDENTE: "Precedente Normativo",
};

/** Detalhe do documento (Figuras 6-7 da RFC), via GET /document/{id}. O corpo (fundamentação,
 *  dispositivo, citações) vem direto dos campos reais — nada de pontos-chave ou trechos de
 *  citação fabricados (RF05/RN03: nunca exibir conteúdo que não vem da fonte). */
export function DecisionDetailPage({ decisionId }: { decisionId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isSaved: isSavedCtx, toggle } = useSaved();
  const [decision, setDecision] = useState<DocumentoDetalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; notFound: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["summary", "grounds", "decision"])
  );

  // A posição no ranking vem da URL (?rank=N), gravada pelo card de /resultados no momento do
  // clique — reflete a ordem que o usuário viu de fato (já filtrada/ordenada localmente), não a
  // ordem crua da resposta de /query. GET /document/{id} não devolve score_rrf (não é propriedade
  // do documento, é da busca que o encontrou), então sem esse parâmetro (ex. veio de "Salvos")
  // não há posição para mostrar.
  const rankParam = searchParams.get("rank");
  const rank = rankParam ? Number(rankParam) : null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDocument(decisionId)
      .then((doc) => {
        if (!cancelled) setDecision(doc);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError({ message: "Documento não encontrado.", notFound: true });
        } else {
          setError({
            message: err instanceof ApiError ? err.message : "Não foi possível conectar ao servidor.",
            notFound: false,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [decisionId]);

  const isSaved = decision ? isSavedCtx(decision.id) : false;

  const formatDate = (dateStr: string | null) =>
    dateStr ? new Date(dateStr).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" }) : "Data não informada";

  const buildFullDocument = (d: DocumentoDetalhe) => {
    const lines: string[] = [];
    lines.push(`${TIPO_LABEL[d.tipo_documento]} — ${d.numero_processo}`, "");
    lines.push(`${d.tribunal} — ${d.turma}`);
    lines.push(`Data: ${formatDate(d.data_julgamento)}`);
    lines.push(`Processo: ${d.numero_processo}`);
    lines.push(`Relator: ${d.relator}`, "");
    lines.push("EMENTA", d.ementa, "");
    if (d.fundamentacao) lines.push("FUNDAMENTAÇÃO", d.fundamentacao, "");
    if (d.acordao) lines.push("DISPOSITIVO", d.acordao, "");
    if (d.referencia_legislativa.length) {
      lines.push("CITAÇÕES NORMATIVAS");
      lines.push(d.referencia_legislativa.map((r) => `• ${r}`).join("\n"), "");
    }
    if (d.link_original) lines.push(`Fonte: ${d.link_original}`);
    return lines.join("\n");
  };

  const copyFullDocument = async () => {
    if (!decision) return;
    const text = buildFullDocument(decision);
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
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  if (loading) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
        <Loader2 className="w-6 h-6 text-[#1A3A5C] dark:text-[#8AB0DC] animate-spin" strokeWidth={2} />
      </main>
    );
  }

  if (error || !decision) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center h-full bg-[#F7F7F9] dark:bg-[#0E0E11] px-6 gap-4">
        <ErrorBanner message={error?.message ?? "Documento não encontrado."} onRetry={error?.notFound ? undefined : () => router.refresh()} />
        <button
          onClick={() => router.push("/resultados")}
          className="text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
          style={{ fontSize: "14.4px" }}
        >
          ← Voltar aos resultados
        </button>
      </main>
    );
  }

  const outcome = provimentoToOutcome(decision.provimento);

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
                {TIPO_LABEL[decision.tipo_documento]} — {decision.numero_processo}
              </h1>
              <div className="flex items-center gap-2 flex-shrink-0">
                <OutcomeBadge outcome={outcome} size="md" suffix=" à tese" />
                {rank !== null && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]">
                    <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                      {rank}º resultado
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 mb-4">
              <MetaItem icon={Scale}>
                <span className="font-medium text-[#4A4A5A] dark:text-[#C4C4CE]">{decision.tribunal}</span>
                <span>—</span>
                <span>{decision.turma}</span>
              </MetaItem>
              <MetaItem icon={Calendar}>
                <span>{formatDate(decision.data_julgamento)}</span>
              </MetaItem>
              <MetaItem icon={FileText}>
                <span className="font-mono text-[#4A4A5A] dark:text-[#C4C4CE]">{decision.numero_processo}</span>
              </MetaItem>
              <MetaItem icon={User}>
                <span>Rel. {decision.relator}</span>
              </MetaItem>
              {decision.gabinete && (
                <MetaItem icon={MapPin}>
                  <span>{decision.gabinete}</span>
                </MetaItem>
              )}
            </div>

            {/* Actions bar */}
            <div className="flex items-center gap-2 pt-3 border-t border-[#F0F0F6] dark:border-[#26262C] flex-wrap">
              <ActionButton
                icon={Bookmark}
                label={isSaved ? "Salvo" : "Salvar"}
                tone={isSaved ? "accent" : "neutral"}
                iconFill={isSaved}
                onClick={() =>
                  toggle({
                    id: decision.id,
                    title: `${TIPO_LABEL[decision.tipo_documento]} — ${decision.numero_processo}`,
                    court: decision.tribunal,
                    chamber: decision.turma,
                    date: decision.data_julgamento ?? "",
                    outcome,
                    relevance: Math.round(decision.score_rrf * 1000) / 10,
                    rapporteur: decision.relator,
                    processNumber: decision.numero_processo,
                  })
                }
              />
              <ActionButton icon={Share2} label="Compartilhar" />
              <ActionButton icon={Download} label="Baixar PDF" />
              <ActionButton
                icon={copied ? CheckCircle2 : Copy}
                label={copied ? "Copiado!" : "Copiar documento"}
                tone={copied ? "success" : "neutral"}
                onClick={copyFullDocument}
                title="Copiar documento completo para a área de transferência"
              />
              <ActionButton
                icon={SlidersHorizontal}
                label="Refinar consulta"
                onClick={() => router.push("/revisao")}
              />
              {decision.link_original && (
                <ActionButton
                  icon={ExternalLink}
                  label="Ver no site oficial"
                  className="ml-auto"
                  onClick={() => window.open(decision.link_original!, "_blank", "noopener,noreferrer")}
                />
              )}
            </div>
          </div>

          {/* Summary */}
          <CollapsibleSection
            icon={Quote}
            iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]"
            iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]"
            title="Ementa"
            expanded={expandedSections.has("summary")}
            onToggle={() => toggleSection("summary")}
          >
            <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed" style={{ fontSize: "14.9px" }}>
              {decision.ementa}
            </p>
          </CollapsibleSection>

          {/* Grounds */}
          {decision.fundamentacao && (
            <CollapsibleSection
              icon={BookOpen}
              iconBg="bg-[#FBF4EC] dark:bg-[#2A2015]"
              iconColor="text-[#7A4A1A] dark:text-[#E0AC6C]"
              title="Fundamentação"
              expanded={expandedSections.has("grounds")}
              onToggle={() => toggleSection("grounds")}
            >
              <div className="prose-sm max-w-none">
                {decision.fundamentacao.split("\n\n").map((paragraph, idx) => (
                  <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                    {paragraph}
                  </p>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Decision */}
          {decision.acordao && (
            <CollapsibleSection
              icon={Scale}
              iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]"
              iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]"
              title="Dispositivo"
              expanded={expandedSections.has("decision")}
              onToggle={() => toggleSection("decision")}
            >
              <div className="bg-[#FAFAFA] dark:bg-[#1C1C21] rounded-xl p-4 border border-[#EBEBF2] dark:border-[#26262C]">
                {decision.acordao.split("\n\n").map((paragraph, idx) => (
                  <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                    {paragraph}
                  </p>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Citations */}
          {decision.referencia_legislativa.length > 0 && (
            <section className="px-5 sm:px-7 py-5">
              <div className="mb-4">
                <SectionHeading icon={Gavel} iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]" iconColor="text-[#6A6A7A] dark:text-[#9494A2]" title="Citações normativas" />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {decision.referencia_legislativa.map((ref, idx) => (
                  <Chip key={idx} tone="neutral">
                    {ref}
                  </Chip>
                ))}
              </div>
            </section>
          )}
        </div>

        <p className="text-[#C8C8D4] dark:text-[#5E5E6A] mt-5" style={{ fontSize: "12.6px" }}>
          Clique nas seções para expandir ou recolher
        </p>
      </div>
    </main>
  );
}
