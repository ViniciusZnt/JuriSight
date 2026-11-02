"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Filter,
  TrendingUp,
  Bookmark,
  AlertCircle,
  Scale,
  Calendar,
  FileText,
  Search,
  ChevronDown,
  Check,
  SlidersHorizontal,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  Download,
  Copy,
  CheckCircle2,
} from "lucide-react";
import { StepIndicator } from "@/components/step-indicator";
import { PageTopbar } from "@/components/ui/page-topbar";
import { MetaItem } from "@/components/ui/meta-item";
import { ActionButton } from "@/components/ui/action-button";
import { Chip } from "@/components/ui/chip";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { type Outcome } from "@/lib/outcome";
import { contarDesfechos, outcomeDe, resumoProvimento, rotuloSelo, PROVIMENTO_LABEL } from "@/lib/provimento";
import { ProvimentoPanel } from "@/components/provimento/provimento-panel";
import { SinteseResultados } from "@/components/resultados/sintese-resultados";
import { RespostaGerada, useRespostaGerada } from "@/components/resultados/resposta-gerada";
import { sintetizar } from "@/lib/sintese";
import {
  compareResultCards,
  ementaComCitacao,
  ementasRepetidas,
  formatarData,
  matchedEntities,
  relevanceRanks,
  titleFromEmenta,
  tituloDoCard,
  truncate,
  TIPO_DOCUMENTO_LABEL,
} from "@/lib/decision-view";
import { useSaved } from "@/lib/saved";
import { useConversations } from "@/lib/conversations";
import { useSearchSession } from "@/lib/search-session";
import { copiarTexto } from "@/lib/utils";

/** Botão "pill" com dropdown — mesmo padrão de filtro usado pelo Jusbrasil (ex: "Em qualquer data ▾"). */
function DropdownPill({
  label,
  active,
  children,
}: {
  label: string;
  active: boolean;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = (returnFocus = false) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div
      className="relative"
      ref={ref}
      onKeyDown={(e) => {
        if (e.key === "Escape") close(true);
      }}
    >
      <button
        ref={triggerRef}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all ${
          active
            ? "bg-[#EFF4FA] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]"
            : "bg-white dark:bg-[#17171B] border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30"
        }`}
        style={{ fontSize: "13.8px", fontWeight: active ? 600 : 400 }}
      >
        {label}
        <ChevronDown className="w-3 h-3" strokeWidth={2} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 sm:right-0 sm:left-auto top-[calc(100%+6px)] z-30 min-w-[220px] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] shadow-[0_8px_28px_rgba(0,0,0,0.12)] p-2"
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

function DropdownOption({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      role="menuitemradio"
      aria-checked={active}
      onClick={onClick}
      className="flex items-center justify-between w-full px-2.5 py-2 rounded-lg text-left hover:bg-[#F6F6F9] dark:hover:bg-[#1C1C21] transition-colors"
      style={{ fontSize: "13.8px", fontWeight: active ? 600 : 400 }}
    >
      <span className={active ? "text-[#1A3A5C] dark:text-[#8AB0DC]" : "text-[#4A4A5A] dark:text-[#C4C4CE]"}>{label}</span>
      {active && <Check className="w-3.5 h-3.5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={2.5} />}
    </button>
  );
}

/** Resultados da busca (Figuras 4-5 da RFC). Lê o ResultCard[] devolvido por POST /query (já
 *  buscado na página de Revisão) do SearchSession — esta página não chama a API de novo; filtros
 *  de provimento/data e ordenação operam sobre o mesmo lote já recebido. */
export function SearchResultsPage() {
  const router = useRouter();
  const { resultados, estrutura, versionNumero, loadVersion } = useSearchSession();
  const { conversations, activeId } = useConversations();
  const { isSaved, toggle } = useSaved();
  const [filter, setFilter] = useState<"all" | Outcome>("all");
  const [sortBy, setSortBy] = useState<"relevance" | "date">("relevance");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [dateFrom, setDateFrom] = useState<string>(""); // yyyy-mm-dd
  const [dateTo, setDateTo] = useState<string>("");
  const [citacao, setCitacao] = useState<string | null>(null); // chip da "Base citada"
  const [tribunal, setTribunal] = useState<string | null>(null);
  const [expandidas, setExpandidas] = useState<Set<string>>(new Set()); // "Ver ementa completa"
  const [copiada, setCopiada] = useState<string | null>(null);

  // Acesso direto à URL sem ter passado por Home/Revisão — não há busca em andamento.
  useEffect(() => {
    if (resultados === null) router.replace("/");
  }, [resultados, router]);

  const results = useMemo(() => resultados ?? [], [resultados]);

  // Versões da conversa ativa (V1, V2, ... — cada "Refinar consulta" bem-sucedido cria
  // uma): já vêm todas carregadas junto com a lista de conversas, trocar de versão aqui é
  // só um swap local (loadVersion), sem chamar a API de novo.
  const versoes = conversations.find((c) => c.id === activeId)?.versions ?? [];

  const ranks = useMemo(() => relevanceRanks(results), [results]);
  const porRank = useMemo(() => [...results].sort((a, b) => ranks.get(a.id)! - ranks.get(b.id)!), [results, ranks]);
  const resposta = useRespostaGerada(estrutura, porRank);
  const sintese = useMemo(() => sintetizar(results), [results]);
  const porId = useMemo(() => new Map(results.map((d) => [d.id, d])), [results]);
  const tribunais = useMemo(() => {
    const n = new Map<string, number>();
    for (const d of results) n.set(d.tribunal, (n.get(d.tribunal) ?? 0) + 1);
    return [...n].sort((a, b) => a[0].localeCompare(b[0], "pt-BR", { numeric: true }));
  }, [results]);
  const repetidas = useMemo(() => ementasRepetidas([...results].sort((a, b) => b.score_rrf - a.score_rrf)), [results]);
  const idsCitacao = new Set(sintese?.base.find((b) => b.rotulo === citacao)?.ids ?? []);

  const limparFiltros = () => {
    setFilter("all");
    setDateFrom("");
    setDateTo("");
    setCitacao(null);
    setTribunal(null);
  };
  // "Decisões que sustentam": tira os filtros para o card existir na lista e rola até ele.
  const irPara = (id: string) => {
    limparFiltros();
    setTimeout(() => document.getElementById(`decisao-${id}`)?.scrollIntoView({ block: "start" }), 0);
  };

  const formatDateShort = (isoDate: string) =>
    new Date(`${isoDate}T00:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });

  const periodLabel =
    dateFrom || dateTo
      ? `${dateFrom ? formatDateShort(dateFrom) : "…"} – ${dateTo ? formatDateShort(dateTo) : "…"}`
      : "Em qualquer data";

  const inPeriod = (dateStr: string | null) => {
    if (!dateStr) return true; // documento sem data conhecida não é excluído pelo filtro de período
    if (dateFrom && dateStr < dateFrom) return false;
    if (dateTo && dateStr > dateTo) return false;
    return true;
  };

  const sortedResults = useMemo(() => {
    const por = sortBy === "date" ? "data" : "relevancia";
    const ordered = [...results].sort((a, b) => compareResultCards(a, b, por));
    return sortDir === "asc" ? ordered.reverse() : ordered;
  }, [results, sortBy, sortDir]);

  const filteredResults = sortedResults
    .filter((d) => filter === "all" || outcomeDe(d) === filter)
    .filter((d) => inPeriod(d.data_julgamento))
    .filter((d) => !citacao || idsCitacao.has(d.id))
    .filter((d) => !tribunal || d.tribunal === tribunal);

  const toggleSave = (d: (typeof results)[number]) => {
    toggle({
      id: d.id,
      title: titleFromEmenta(d.ementa),
      court: d.tribunal,
      chamber: d.turma,
      date: d.data_julgamento ?? "",
      outcome: outcomeDe(d),
      relevance: ranks.get(d.id) ?? 0,
      rapporteur: d.relator,
      processNumber: d.numero_processo,
    });
  };

  const formatDate = (dateStr: string | null) => formatarData(dateStr, "short");
  const formatDateLong = (dateStr: string | null) => formatarData(dateStr, "long");
  const alternarEmenta = (id: string) =>
    setExpandidas((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const { favorable: favorableCount, unfavorable: unfavorableCount, neutral: neutralCount } = contarDesfechos(results);

  // FA04 (RFC 3.2) — filtro de provimento aplicado mas com poucos resultados.
  const lowProvimentoResults = filter !== "all" && filteredResults.length > 0 && filteredResults.length < 3;

  // Exporta os resultados filtrados/ordenados como estão em tela — só formatação local, sem backend.
  const exportResults = () => {
    const lines = filteredResults.map((d, idx) =>
      [
        `${idx + 1}. ${titleFromEmenta(d.ementa)}`,
        `   ${d.tribunal} — ${d.turma} · ${formatDateLong(d.data_julgamento)}`,
        `   Processo: ${d.numero_processo} · Rel. ${d.relator}`,
        `   Provimento: ${d.classificacao_provimento ? resumoProvimento(d.classificacao_provimento) : PROVIMENTO_LABEL[d.provimento]} · Relevância: #${ranks.get(d.id)} de ${results.length}`,
        `   ${truncate(d.ementa, 600)}`,
      ].join("\n")
    );
    const header = `JuriSight — Jurisprudências (${filteredResults.length} de ${results.length} resultados)\nExportado em ${new Date().toLocaleString("pt-BR")}\n`;
    const blob = new Blob([header, "\n", lines.join("\n\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jurisight-resultados.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (resultados === null) return null; // redirecionando para "/" (ver efeito acima)

  return (
    <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <PageTopbar
        crumbs={[
          { label: "Início", onClick: () => router.push("/") },
          { label: "Revisão", onClick: () => router.push("/revisao") },
          { label: "Jurisprudências" },
        ]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-4 sm:px-8 py-4 pb-10">
        <StepIndicator current={2} />

        <RespostaGerada resposta={resposta} ordem={porRank} onIr={irPara} />

        {/* Summary banner */}
        <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none px-6 py-4 mb-6 flex flex-col sm:flex-row flex-wrap sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex-shrink-0">
              <Scale className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
            </div>
            <div>
              <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "16.7px", fontWeight: 600 }}>
                {filteredResults.length} {filteredResults.length === 1 ? "decisão encontrada" : "decisões encontradas"}
              </h2>
              {estrutura?.tese_central && (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
                  Alinhadas à tese: &ldquo;{truncate(estrutura.tese_central, 90)}&rdquo;
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap sm:flex-shrink-0 items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#EDF7F2] dark:bg-[#122A1E] border border-[#BDE0CF] dark:border-[#1E4A34]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#2D8A5F] dark:bg-[#3DA372]" />
              <span className="text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                {favorableCount} {favorableCount === 1 ? "favorável" : "favoráveis"}
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#FBF0F0] dark:bg-[#2A1517] border border-[#E8C2C2] dark:border-[#4A2529]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#C44040] dark:bg-[#D96B6B]" />
              <span className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                {unfavorableCount} {unfavorableCount === 1 ? "desfavorável" : "desfavoráveis"}
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#F5F5F8] dark:bg-[#1C1C21] border border-[#DCDCE8] dark:border-[#2A2A32]">
              <div className="w-1.5 h-1.5 rounded-full bg-[#9090A8] dark:bg-[#7C7C88]" />
              <span className="text-[#6A6A7A] dark:text-[#9494A2]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                {neutralCount} neutro{neutralCount === 1 ? "" : "s"}
              </span>
            </div>
          </div>
          {sintese && (
            <SinteseResultados sintese={sintese} porId={porId} ranks={ranks} citacao={citacao} onCitacao={setCitacao} onIr={irPara} />
          )}
        </div>

        {/* Versões (V1/V2/...) e refinar consulta */}
        <div className="w-full max-w-[800px] flex items-center justify-between gap-3 mb-3">
          {versoes.length > 1 ? (
            <DropdownPill label={`Versão V${versionNumero ?? versoes[versoes.length - 1].numero}`} active={false}>
              {(close) => (
                <>
                  {[...versoes].reverse().map((v) => (
                    <DropdownOption
                      key={v.numero}
                      label={`V${v.numero}${v.numero === versoes.length ? " (mais recente)" : ""}`}
                      active={v.numero === versionNumero}
                      onClick={() => {
                        loadVersion(v);
                        close();
                      }}
                    />
                  ))}
                </>
              )}
            </DropdownPill>
          ) : (
            <span />
          )}
          <button
            onClick={() => router.push("/revisao")}
            className="flex items-center gap-1.5 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
            style={{ fontSize: "13.8px", fontWeight: 500 }}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" strokeWidth={1.8} />
            Refinar consulta
          </button>
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
              Todas ({results.length})
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

          <div className="flex flex-wrap items-center gap-2">
            <DropdownPill label={tribunal ?? "Todos os tribunais"} active={tribunal !== null}>
              {(close) => (
                <div className="p-1 max-h-[320px] overflow-y-auto">
                  {[[null, results.length] as const, ...tribunais].map(([t, n]) => (
                    <DropdownOption
                      key={t ?? "todos"}
                      label={`${t ?? "Todos os tribunais"} (${n})`}
                      active={tribunal === t}
                      onClick={() => {
                        setTribunal(t);
                        close();
                      }}
                    />
                  ))}
                </div>
              )}
            </DropdownPill>

            <DropdownPill label={periodLabel} active={dateFrom !== "" || dateTo !== ""}>
              {(close) => (
                <div className="p-1">
                  <p className="px-2 pb-1.5 text-[#9090A8] dark:text-[#7C7C88] uppercase tracking-[0.06em]" style={{ fontSize: "11.5px", fontWeight: 600 }}>
                    Período de julgamento
                  </p>
                  <div className="flex flex-col gap-2 px-2 pb-2" style={{ width: "220px" }}>
                    <label className="flex flex-col gap-1">
                      <span className="text-[#9090A8] dark:text-[#7C7C88]" style={{ fontSize: "12.1px" }}>De</span>
                      <input
                        type="date"
                        value={dateFrom}
                        max={dateTo || undefined}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className="rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#1C1C21] text-[#4A4A5A] dark:text-[#C4C4CE] px-2 py-1.5 outline-none"
                        style={{ fontSize: "13.2px", colorScheme: "light dark" }}
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[#9090A8] dark:text-[#7C7C88]" style={{ fontSize: "12.1px" }}>Até</span>
                      <input
                        type="date"
                        value={dateTo}
                        min={dateFrom || undefined}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#1C1C21] text-[#4A4A5A] dark:text-[#C4C4CE] px-2 py-1.5 outline-none"
                        style={{ fontSize: "13.2px", colorScheme: "light dark" }}
                      />
                    </label>
                  </div>
                  <div className="flex items-center justify-between px-2 pt-1 border-t border-[#F0F0F6] dark:border-[#26262C]">
                    <button
                      onClick={() => {
                        setDateFrom("");
                        setDateTo("");
                      }}
                      className="text-[#9090A8] dark:text-[#7C7C88] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] py-1.5"
                      style={{ fontSize: "12.6px" }}
                    >
                      Limpar
                    </button>
                    <button
                      onClick={close}
                      className="rounded-lg bg-[#1A3A5C] text-white px-3 py-1.5 hover:bg-[#1E4570] transition-colors"
                      style={{ fontSize: "12.6px", fontWeight: 600 }}
                    >
                      Aplicar
                    </button>
                  </div>
                </div>
              )}
            </DropdownPill>

            <DropdownPill label={sortBy === "relevance" ? "Relevância" : "Data"} active={false}>
              {(close) => (
                <div className="p-1">
                  <DropdownOption
                    label="Relevância"
                    active={sortBy === "relevance"}
                    onClick={() => {
                      setSortBy("relevance");
                      close();
                    }}
                  />
                  <DropdownOption
                    label="Data"
                    active={sortBy === "date"}
                    onClick={() => {
                      setSortBy("date");
                      close();
                    }}
                  />
                </div>
              )}
            </DropdownPill>

            <button
              onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
              className="flex items-center justify-center w-[34px] h-[34px] rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#17171B] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30 transition-all"
              title={sortDir === "asc" ? "Ordem crescente — clique para inverter" : "Ordem decrescente — clique para inverter"}
              aria-label={sortDir === "asc" ? "Ordem crescente — clique para inverter para decrescente" : "Ordem decrescente — clique para inverter para crescente"}
            >
              {sortDir === "asc" ? (
                <ArrowUp className="w-3.5 h-3.5" strokeWidth={2} />
              ) : (
                <ArrowDown className="w-3.5 h-3.5" strokeWidth={2} />
              )}
            </button>
          </div>
        </div>

        {/* FA04 — filtro de provimento com poucos resultados */}
        {lowProvimentoResults && (
          <div className="w-full max-w-[800px] flex items-start gap-2.5 rounded-xl border border-[#EDD9BC] dark:border-[#4A3A22] bg-[#FBF4EC] dark:bg-[#2A2015] px-4 py-3 mb-4">
            <AlertTriangle className="w-4 h-4 text-[#8A5A1E] dark:text-[#E0AC6C] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
            <p className="text-[#6B3B0A] dark:text-[#E0AC6C]" style={{ fontSize: "13.8px" }}>
              Apenas {filteredResults.length} resultado{filteredResults.length === 1 ? "" : "s"} encontrado
              {filteredResults.length === 1 ? "" : "s"} com provimento {filter === "favorable" ? "favorável" : "desfavorável"}.{" "}
              <button onClick={() => setFilter("all")} className="underline hover:no-underline" style={{ fontWeight: 600 }}>
                Considere remover o filtro
              </button>{" "}
              para ver todas as decisões sobre o tema.
            </p>
          </div>
        )}

        {/* Results list */}
        {filteredResults.length === 0 ? (
          <div className="w-full max-w-[800px] flex flex-col items-center justify-center py-20 text-center">
            <div className="w-12 h-12 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex items-center justify-center mb-4">
              <Search className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
            </div>
            <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "17.8px", fontWeight: 600 }}>
              Nenhum documento encontrado
            </h2>
            <p className="mt-2 max-w-sm text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.9px" }}>
              Nenhum documento encontrado para esta consulta. Tente ampliar a intenção argumentativa ou remover
              filtros de provimento e período.
            </p>
            <div className="flex items-center gap-3 mt-5">
              {(filter !== "all" || dateFrom || dateTo || citacao || tribunal) && (
                <button
                  onClick={limparFiltros}
                  className="px-3.5 py-2 rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30 transition-all"
                  style={{ fontSize: "13.8px" }}
                >
                  Remover filtros
                </button>
              )}
              <button
                onClick={() => router.push("/revisao")}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#1A3A5C] text-white hover:bg-[#1E4570] transition-colors"
                style={{ fontSize: "13.8px", fontWeight: 600 }}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" strokeWidth={1.8} />
                Refinar consulta
              </button>
            </div>
          </div>
        ) : (
          <div className="w-full max-w-[800px] space-y-4">
            {filteredResults.map((decision) => {
              const saved = isSaved(decision.id);
              const title = tituloDoCard(decision);
              const outcome = outcomeDe(decision);
              const rank = ranks.get(decision.id);
              const entidades = matchedEntities(estrutura, decision.ementa);
              const original = repetidas.get(decision.id);
              const expandida = expandidas.has(decision.id);

              return (
                // O título é o link (Ctrl+clique, nova aba, Tab); o ::after dele cobre o card inteiro
                // para o clique em qualquer ponto abrir a decisão. Controles internos ficam com z-10.
                <div
                  key={decision.id}
                  id={`decisao-${decision.id}`}
                  className="relative scroll-mt-16 target:ring-2 target:ring-[#1A3A5C]/40 dark:target:ring-[#8AB0DC]/50 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] hover:shadow-[0_3px_16px_rgba(0,0,0,0.09)] dark:shadow-none dark:hover:border-[#33333C] transition-all overflow-hidden group"
                >
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
                        <div
                          title={`${rank}º mais relevante de ${results.length} nesta busca`}
                          aria-label={`${rank}º mais relevante de ${results.length} nesta busca`}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#FAFAFA] dark:bg-[#1C1C21] border border-[#EBEBF2] dark:border-[#26262C]"
                        >
                          <TrendingUp className="w-3 h-3 text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
                          <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
                            #{rank}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
                      <MetaItem icon={Scale} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span>{decision.tribunal} — {decision.turma}</span>
                      </MetaItem>
                      <MetaItem icon={Calendar} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span>{formatDate(decision.data_julgamento)}</span>
                      </MetaItem>
                      <MetaItem icon={FileText} className="" iconClassName="" iconSize="w-3 h-3" fontSize="13.2px" gap="gap-1.5">
                        <span className="font-mono">{decision.numero_processo}</span>
                      </MetaItem>
                    </div>
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
                        onClick={() => alternarEmenta(decision.id)}
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
                      {original && (
                        <Chip tone="amber" size="sm">
                          Ementa igual à de #{ranks.get(original)}
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
                        icon={copiada === decision.id ? CheckCircle2 : Copy}
                        label={copiada === decision.id ? "Copiada!" : "Copiar ementa"}
                        tone={copiada === decision.id ? "success" : "neutral"}
                        size="sm"
                        className="relative z-10"
                        title="Copiar a ementa com a linha de citação (tribunal, turma, processo, data, relator)"
                        onClick={() =>
                          copiarTexto(ementaComCitacao(decision)).then(() => {
                            setCopiada(decision.id);
                            setTimeout(() => setCopiada(null), 2000);
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
                        onClick={() => toggleSave(decision)}
                      />
                    </div>
                  </div>
                </div>
              );
            })}

            <div className="flex justify-center pt-2">
              <button
                onClick={exportResults}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#17171B] text-[#4A4A5A] dark:text-[#C4C4CE] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30 hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] transition-all"
                style={{ fontSize: "13.8px", fontWeight: 500 }}
              >
                <Download className="w-3.5 h-3.5" strokeWidth={1.8} />
                Exportar resultados
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
