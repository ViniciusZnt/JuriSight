"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
  AlertCircle,
  Quote,
  BookOpen,
  Gavel,
  TrendingUp,
  SlidersHorizontal,
} from "lucide-react";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { SectionHeading } from "@/components/ui/section-heading";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { findDecision } from "@/lib/mock-decisions";
import { useSaved } from "@/lib/saved";

/** Detalhe do acórdão (Figuras 6-7 da RFC). Dados mockados até a API existir; título, meta e
 *  resumo vêm da mesma fonte da lista de resultados — o corpo (fundamentação, dispositivo,
 *  citações) é ilustrativo até o backend existir. */
export function DecisionDetailPage({ decisionId }: { decisionId: string }) {
  const router = useRouter();
  const { isSaved: isSavedCtx, toggle } = useSaved();
  const [copied, setCopied] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(["summary", "grounds", "decision"])
  );

  const base = findDecision(decisionId);
  const isSaved = isSavedCtx(base.id);

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });

  // Caso 1 é o exemplo oficial das Figuras 6-7 da RFC — corpo integral e específico.
  // Os demais usam um corpo ilustrativo derivado dos próprios dados do card, para nunca exibir
  // fundamentação/dispositivo de um caso diferente do título mostrado (RF06 — fonte real, sem
  // conteúdo inventado que não corresponda ao documento).
  const decision =
    base.id === "1"
      ? {
          ...base,
          origin: "TRT-1 (Rio de Janeiro)",
          keyPoints: [
            "Exposição habitual e permanente a benzeno (agente cancerígeno)",
            "Empresa tinha ciência dos riscos através de PPRA e PCMSO",
            "EPI fornecido não foi considerado eficaz pela perícia",
            "Aplicação do grau máximo (40%) por agente químico cancerígeno",
            "Responsabilidade objetiva do empregador por risco ambiental",
          ],
          grounds: `A controvérsia consiste em definir se o reclamante faz jus ao pagamento de adicional de insalubridade em grau máximo, em face da alegada exposição a agente químico cancerígeno (benzeno).

O laudo pericial acostado aos autos concluiu que o reclamante laborava exposto, de forma habitual e permanente, a hidrocarbonetos aromáticos, especificamente benzeno, em concentrações superiores aos limites de tolerância estabelecidos no Anexo 13-A da NR-15.

A prova documental demonstra que a reclamada tinha pleno conhecimento dos riscos ambientais, conforme se depreende do PPRA (Programa de Prevenção de Riscos Ambientais) e do PCMSO (Programa de Controle Médico de Saúde Ocupacional) apresentados, os quais identificavam expressamente a presença de benzeno nas atividades desenvolvidas pelo autor.

No que tange ao fornecimento de Equipamentos de Proteção Individual (EPI), embora a reclamada tenha apresentado fichas de entrega, o perito judicial esclareceu que os equipamentos fornecidos não eram capazes de neutralizar ou reduzir a exposição do trabalhador ao agente nocivo a níveis toleráveis, caracterizando-se a ineficácia do EPI.

Ressalte-se que, tratando-se de agente cancerígeno, a jurisprudência consolidada desta Corte é no sentido de que o adicional de insalubridade é devido mesmo com o fornecimento de EPI, ante a impossibilidade de neutralização do risco à saúde (Súmula 448 do TST).`,
          decision: `Ante o exposto, NEGO PROVIMENTO ao recurso de revista patronal.

ISTO POSTO

ACORDAM os Ministros da Terceira Turma do Tribunal Superior do Trabalho, por unanimidade, conhecer do recurso de revista por contrariedade à Súmula nº 448 do TST, e, no mérito, negar-lhe provimento, mantendo integralmente a condenação ao pagamento de adicional de insalubridade em grau máximo.

Brasília, 28 de abril de 2025.

Firmado por assinatura digital (Lei nº 11.419/2006)

ALBERTO BRESCIANI
Ministro Relator`,
          citations: [
            {
              reference: "CLT, art. 192",
              text: "O exercício de trabalho em condições insalubres, acima dos limites de tolerância estabelecidos pelo Ministério do Trabalho, assegura a percepção de adicional respectivamente de 40% (quarenta por cento), 20% (vinte por cento) e 10% (dez por cento) do salário-mínimo da região, segundo se classifiquem nos graus máximo, médio e mínimo.",
            },
            {
              reference: "Súmula 448 TST",
              text: "A exposição do empregado a agente nocivo cancerígeno ensejadora da aposentadoria especial de que trata o art. 57, § 8º, da Lei nº 8.213/91 é insuscetível de neutralização pela utilização de Equipamento de Proteção Individual - EPI.",
            },
            {
              reference: "NR-15, Anexo 13-A",
              text: "Operações com benzeno: valor de referência tecnológico de 1 ppm (valor teto). Grau máximo de insalubridade.",
            },
          ],
        }
      : {
          ...base,
          origin: base.court,
          keyPoints: [
            ...base.matchedEntities.map((e) => `Elemento do contexto identificado na decisão: ${e}`),
            `Fundamentos normativos citados: ${base.tags.join(", ")}`,
          ],
          grounds: `${base.summary}

A controvérsia foi analisada pela ${base.chamber} do ${base.court}, sob relatoria de ${base.rapporteur}, nos autos do processo ${base.processNumber}, julgado em ${formatDate(base.date)}.`,
          decision: `Ante o exposto, ${
            base.outcome === "favorable"
              ? "NEGO PROVIMENTO ao recurso patronal, mantendo a decisão que reconheceu o pedido do reclamante."
              : base.outcome === "unfavorable"
                ? "DOU PROVIMENTO ao recurso patronal, reformando a decisão de origem e afastando o pedido do reclamante."
                : "NEGO PROVIMENTO ao recurso, mantendo a decisão de origem quanto ao mérito."
          }

ACORDAM os membros da ${base.chamber} do ${base.court}, por unanimidade, nos termos do voto do(a) relator(a).

${formatDate(base.date)}.

${base.rapporteur}
Relator(a)`,
          citations: base.tags.map((tag) => ({
            reference: tag,
            text: "Dispositivo citado como fundamento normativo desta decisão.",
          })),
        };

  const buildFullDocument = () => {
    const lines: string[] = [];
    lines.push(decision.title, "");
    lines.push(`${decision.court} — ${decision.chamber}`);
    lines.push(`Data: ${formatDate(decision.date)}`);
    lines.push(`Processo: ${decision.processNumber}`);
    lines.push(`Relator: ${decision.rapporteur}`);
    lines.push(`Origem: ${decision.origin}`);
    lines.push(`Relevância: ${decision.relevance}%`, "");
    if (decision.matchedEntities.length) {
      lines.push("ENTIDADES CORRESPONDENTES");
      lines.push(decision.matchedEntities.map((e) => `• ${e}`).join("\n"), "");
    }
    lines.push("RESUMO DA DECISÃO", decision.summary, "");
    lines.push("PONTOS-CHAVE", decision.keyPoints.map((p) => `• ${p}`).join("\n"), "");
    lines.push("FUNDAMENTAÇÃO", decision.grounds, "");
    lines.push("DISPOSITIVO", decision.decision, "");
    lines.push("CITAÇÕES NORMATIVAS");
    decision.citations.forEach((c) => lines.push(c.reference, `"${c.text}"`, ""));
    lines.push(`Tags: ${decision.tags.join(", ")}`);
    return lines.join("\n");
  };

  const copyFullDocument = async () => {
    const text = buildFullDocument();
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
                {decision.title}
              </h1>
              <div className="flex items-center gap-2 flex-shrink-0">
                <OutcomeBadge outcome={decision.outcome} size="md" suffix=" à tese" />
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]">
                  <TrendingUp className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                  <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                    {decision.relevance}% relevância
                  </span>
                </div>
              </div>
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 mb-4">
              <MetaItem icon={Scale}>
                <span className="font-medium text-[#4A4A5A] dark:text-[#C4C4CE]">{decision.court}</span>
                <span>—</span>
                <span>{decision.chamber}</span>
              </MetaItem>
              <MetaItem icon={Calendar}>
                <span>{formatDate(decision.date)}</span>
              </MetaItem>
              <MetaItem icon={FileText}>
                <span className="font-mono text-[#4A4A5A] dark:text-[#C4C4CE]">{decision.processNumber}</span>
                <button className="ml-1 hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC]">
                  <Copy className="w-3 h-3" strokeWidth={1.8} />
                </button>
              </MetaItem>
              <MetaItem icon={User}>
                <span>Rel. {decision.rapporteur}</span>
              </MetaItem>
              <MetaItem icon={MapPin}>
                <span>Origem: {decision.origin}</span>
              </MetaItem>
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
                    title: decision.title,
                    court: decision.court,
                    chamber: decision.chamber,
                    date: decision.date,
                    outcome: decision.outcome,
                    relevance: decision.relevance,
                    rapporteur: decision.rapporteur,
                    processNumber: decision.processNumber,
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
              <ActionButton icon={ExternalLink} label="Ver no site oficial" className="ml-auto" />
            </div>
          </div>

          {/* Matched entities */}
          {decision.matchedEntities.length > 0 && (
            <div className="px-5 sm:px-7 py-4 bg-[#FAFBFF] dark:bg-[#15191F] border-b border-[#F0F0F6] dark:border-[#26262C]">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
                <div className="flex-1">
                  <span className="text-[#4A4A5A] dark:text-[#C4C4CE] block mb-2" style={{ fontSize: "13.2px", fontWeight: 600 }}>
                    Entidades correspondentes ao seu contexto:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {decision.matchedEntities.map((entity, idx) => (
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
            title="Resumo da decisão"
            expanded={expandedSections.has("summary")}
            onToggle={() => toggleSection("summary")}
          >
            <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed" style={{ fontSize: "14.9px" }}>
              {decision.summary}
            </p>
          </CollapsibleSection>

          {/* Key points */}
          <section className="px-5 sm:px-7 py-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="mb-3">
              <SectionHeading icon={Gavel} iconBg="bg-[#EDF7F2] dark:bg-[#122A1E]" iconColor="text-[#1E6B4A] dark:text-[#6FCB9A]" title="Pontos-chave" />
            </div>
            <ul className="space-y-2">
              {decision.keyPoints.map((point, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#2D8A5F] dark:bg-[#3DA372] mt-1.5 flex-shrink-0" />
                  <span className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "14.4px" }}>
                    {point}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* Grounds */}
          <CollapsibleSection
            icon={BookOpen}
            iconBg="bg-[#FBF4EC] dark:bg-[#2A2015]"
            iconColor="text-[#7A4A1A] dark:text-[#E0AC6C]"
            title="Fundamentação"
            expanded={expandedSections.has("grounds")}
            onToggle={() => toggleSection("grounds")}
          >
            <div className="prose-sm max-w-none">
              {decision.grounds.split("\n\n").map((paragraph, idx) => (
                <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                  {paragraph}
                </p>
              ))}
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
              {decision.decision.split("\n\n").map((paragraph, idx) => (
                <p key={idx} className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed mb-3 last:mb-0" style={{ fontSize: "14.4px", textAlign: "justify" }}>
                  {paragraph}
                </p>
              ))}
            </div>
          </CollapsibleSection>

          {/* Citations */}
          <section className="px-5 sm:px-7 py-5">
            <div className="mb-4">
              <SectionHeading icon={FileText} iconBg="bg-[#F5F5F8] dark:bg-[#1C1C21]" iconColor="text-[#6A6A7A] dark:text-[#9494A2]" title="Citações normativas" />
            </div>
            <div className="space-y-3">
              {decision.citations.map((citation, idx) => (
                <div key={idx} className="bg-[#FAFAFA] dark:bg-[#1C1C21] rounded-xl p-4 border border-[#EBEBF2] dark:border-[#26262C]">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded bg-[#EEF3FB] dark:bg-[#1A2A3C] border border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "12.1px", fontWeight: 600 }}>
                      {citation.reference}
                    </span>
                  </div>
                  <p className="text-[#6B6B80] dark:text-[#A6A6B4] leading-relaxed italic" style={{ fontSize: "13.8px" }}>
                    &ldquo;{citation.text}&rdquo;
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Tags */}
          <div className="px-5 sm:px-7 py-4 bg-[#FAFAFA] dark:bg-[#1C1C21] border-t border-[#F0F0F6] dark:border-[#26262C]">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[#9090A8] dark:text-[#7C7C88]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                Tags:
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {decision.tags.map((tag, idx) => (
                <Chip key={idx} tone="neutral">
                  {tag}
                </Chip>
              ))}
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
