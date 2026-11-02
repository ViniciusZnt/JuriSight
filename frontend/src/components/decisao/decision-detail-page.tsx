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
  ScrollText,
} from "lucide-react";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { SectionHeading } from "@/components/ui/section-heading";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ProvimentoPanel } from "@/components/provimento/provimento-panel";
import { PROVIMENTO_LABEL, RESULTADO_LABEL, outcomeDe } from "@/lib/provimento";
import {
  dispositivoDe,
  ementaComCitacao,
  formatarData,
  matchedEntities,
  paragrafos,
  relevanceRanks,
  titleFromEmenta,
  TIPO_DOCUMENTO_LABEL,
} from "@/lib/decision-view";
import { copiarTexto } from "@/lib/utils";
import { useSaved } from "@/lib/saved";
import { useSearchSession } from "@/lib/search-session";
import { getDocument, ApiError, type DocumentoDetalhe } from "@/lib/api";

/** Texto do documento em parágrafos, alinhado à esquerda; acima de ~3 mil caracteres mostra o
 *  começo e um botão para ler o resto sem sair da página. */
function TextoLongo({ texto, vazio }: { texto: string; vazio: string }) {
  const [inteiro, setInteiro] = useState(false);
  if (!texto.trim()) {
    return <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px" }}>{vazio}</p>;
  }
  const longo = texto.length > 3000;
  return (
    <>
      {paragrafos(longo && !inteiro ? `${texto.slice(0, 3000).replace(/\s+\S*$/, "")}…` : texto).map((p, idx) => (
        <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px" }}>
          {p}
        </p>
      ))}
      {longo && (
        <button
          onClick={() => setInteiro((v) => !v)}
          aria-expanded={inteiro}
          className="mt-1 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
          style={{ fontSize: "13.8px", fontWeight: 500 }}
        >
          {inteiro ? "Mostrar menos" : `Ler o texto todo (${Math.round(texto.length / 1000)} mil caracteres)`}
        </button>
      )}
    </>
  );
}

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
  const [ementaCopiada, setEmentaCopiada] = useState(false);
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

  const formatDate = (dateStr: string | null) => formatarData(dateStr, "long");

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const copyText = (text: string, onDone: () => void) => copiarTexto(text).then(onDone);

  if (error) {
    return (
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
        <PageTopbar bordered crumbs={[{ label: "Início", onClick: () => router.push("/resultados") }, { label: "Decisão" }]} />
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
        <PageTopbar bordered crumbs={[{ label: "Início", onClick: () => router.push("/resultados") }, { label: "Decisão" }]} />
        <div className="flex-1 flex flex-col items-center justify-center py-24">
          <Loader2 className="w-6 h-6 text-[#1A3A5C] dark:text-[#8AB0DC] animate-spin" strokeWidth={2} />
          <p className="mt-3 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px" }}>Carregando decisão…</p>
        </div>
      </main>
    );
  }

  const title = titleFromEmenta(doc.ementa);
  const outcome = outcomeDe(doc);
  const origin = doc.gabinete || doc.tribunal;
  const entidades = matchedEntities(estrutura, `${doc.ementa} ${doc.fundamentacao} ${doc.acordao}`);
  const relevance = resultados ? (relevanceRanks(resultados).get(doc.id) ?? null) : null;
  const relevanceLabel = `#${relevance} de ${resultados?.length} em relevância`;
  const dispositivo = dispositivoDe(doc.acordao);
  const identificacao = [TIPO_DOCUMENTO_LABEL[doc.tipo_documento], doc.sigla_classe, doc.tribunal, doc.turma].filter(Boolean).join(" · ");

  const buildFullDocument = () => {
    const lines: string[] = [];
    lines.push(title, "");
    lines.push(`${doc.tribunal} — ${doc.turma}`);
    lines.push(`Data: ${formatDate(doc.data_julgamento)}`);
    lines.push(`Processo: ${doc.numero_processo}`);
    lines.push(`Relator: ${doc.relator}`);
    lines.push(`Origem: ${origin}`);
    if (relevance !== null) lines.push(`Relevância: ${relevanceLabel}`);
    lines.push("");
    if (entidades.length) {
      lines.push("ENTIDADES CORRESPONDENTES");
      lines.push(entidades.map((e) => `• ${e}`).join("\n"), "");
    }
    lines.push("EMENTA", doc.ementa, "");
    if (doc.relatorio) lines.push("RELATÓRIO", doc.relatorio, "");
    if (doc.fundamentacao) lines.push("FUNDAMENTAÇÃO", doc.fundamentacao, "");
    if (dispositivo) lines.push("DISPOSITIVO", dispositivo, "");
    if (doc.acordao) lines.push("INTEIRO TEOR", doc.acordao, "");
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
        crumbs={[
          { label: "Início", onClick: () => router.push("/resultados") },
          { label: "Jurisprudências", onClick: () => router.push("/resultados") },
          { label: "Decisão" },
        ]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-4 sm:px-8 py-6 pb-10">
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
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 sm:gap-4 mb-4">
              <div className="flex-1">
                <p className="text-[#6B6B80] dark:text-[#A6A6B4] mb-1" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                  {identificacao}
                </p>
                <h1 className="text-[#0F1117] dark:text-[#ECECEF] leading-tight" style={{ fontSize: "20.7px", fontWeight: 600 }}>
                  {title}
                </h1>
              </div>
              <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                <OutcomeBadge outcome={outcome} size="md" suffix=" à tese" />
                {relevance !== null && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]">
                    <TrendingUp className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                    <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                      {relevanceLabel}
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
            <div className="flex items-center gap-2 pt-3 border-t border-[#F0F0F6] dark:border-[#26262C] flex-wrap *:grow sm:*:grow-0">
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
                <a href={doc.link_original} target="_blank" rel="noopener noreferrer" className="sm:ml-auto">
                  <ActionButton icon={ExternalLink} label="Ver no site oficial" className="w-full" />
                </a>
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
            <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed whitespace-pre-line" style={{ fontSize: "14.9px" }}>
              {doc.ementa || "Ementa não disponível para este documento."}
            </p>
            {doc.ementa && (
              <ActionButton
                icon={ementaCopiada ? CheckCircle2 : Copy}
                label={ementaCopiada ? "Copiada!" : "Copiar ementa com citação"}
                tone={ementaCopiada ? "success" : "neutral"}
                size="sm"
                className="mt-3"
                title="Copiar a ementa com a linha de citação (tribunal, turma, processo, data, relator)"
                onClick={() => copyText(ementaComCitacao(doc), () => { setEmentaCopiada(true); setTimeout(() => setEmentaCopiada(false), 2000); })}
              />
            )}
          </CollapsibleSection>

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

          {/* Provimento (Jev) */}
          <section className="px-5 sm:px-7 py-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="mb-3">
              <SectionHeading icon={Scale} iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]" iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]" title="Provimento" />
            </div>
            <ProvimentoPanel documentoId={doc.id} provimento={doc.provimento} classificacao={doc.classificacao_provimento} />
          </section>

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
              <TextoLongo texto={doc.relatorio} vazio="" />
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
            <TextoLongo texto={doc.fundamentacao} vazio="Fundamentação não disponível para este documento." />
            {doc.fundamentacao.length < 1500 && doc.acordao.length > 5000 && (
              <p className="mt-3 text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "13.2px" }}>
                Na fonte, esta seção veio curta; o texto completo está em &ldquo;Inteiro teor&rdquo;, abaixo.
              </p>
            )}
          </CollapsibleSection>

          {/* Dispositivo: trecho final do inteiro teor (o campo `acordao` traz o acórdão inteiro) */}
          {dispositivo && (
            <CollapsibleSection
              icon={Scale}
              iconBg="bg-[#EFF4FA] dark:bg-[#1A2A3C]"
              iconColor="text-[#1A3A5C] dark:text-[#8AB0DC]"
              title="Dispositivo"
              expanded={expandedSections.has("decision")}
              onToggle={() => toggleSection("decision")}
            >
              <TextoLongo texto={dispositivo} vazio="" />
            </CollapsibleSection>
          )}

          <CollapsibleSection
            icon={ScrollText}
            iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]"
            iconColor="text-[#6A6A7A] dark:text-[#9494A2]"
            title="Inteiro teor"
            expanded={expandedSections.has("teor")}
            onToggle={() => toggleSection("teor")}
          >
            <TextoLongo texto={doc.acordao} vazio="Inteiro teor não disponível para este documento." />
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
              <TextoLongo texto={doc.votos} vazio="" />
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
              <Chip tone="neutral">
                {doc.classificacao_provimento ? RESULTADO_LABEL[doc.classificacao_provimento.resultado] : PROVIMENTO_LABEL[doc.provimento]}
              </Chip>
            </div>
          </div>
        </div>

        <p className="text-[#C8C8D4] dark:text-[#5E5E6A] mt-5" style={{ fontSize: "12.6px" }}>
          Clique nas seções para expandir ou recolher
        </p>
      </div>
    </main>
  );
}
