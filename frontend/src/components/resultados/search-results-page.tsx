"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Scale,
  Calendar,
  TrendingUp,
  Search,
  ChevronDown,
  Check,
  SlidersHorizontal,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  Download,
} from "lucide-react";
import { StepIndicator } from "@/components/step-indicator";
import { PageTopbar } from "@/components/ui/page-topbar";
import { type Outcome } from "@/lib/outcome";
import { contarDesfechos, outcomeDe, resumoProvimento, PROVIMENTO_LABEL } from "@/lib/provimento";
import { ResumoDecisoes } from "@/components/resultados/resumo-decisoes";
import { ResultadoCard } from "@/components/resultados/resultado-card";
import { FaixaLivre } from "@/components/resultados/faixa-livre";
import { contarFiltros, temFiltroRestrito, rotuloTribunal, ROTULO_FASE, type ContagemFiltros } from "@/lib/api";
import { useRespostaGerada } from "@/components/resultados/resposta-gerada";
import { ParecerPesquisa } from "@/components/resultados/parecer-pesquisa";
import { sintetizar } from "@/lib/sintese";
import {
  compareResultCards,
  ementasRepetidas,
  formatarData,
  relevanceRanks,
  titleFromEmenta,
  truncate,
} from "@/lib/decision-view";
import { useFecharAoClicarFora } from "@/lib/use-fechar-ao-clicar-fora";
import { useConversations } from "@/lib/conversations";
import { useSearchSession } from "@/lib/search-session";

/** Segmentos da barra de filtros, com as cores dos selos de desfecho. */
const SEGMENTOS: { valor: "all" | Outcome; rotulo: string; cor: string | null; ativo: string }[] = [
  { valor: "all", rotulo: "Todas", cor: null, ativo: "bg-[#1A3A5C] dark:bg-[#8AB0DC] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(26,58,92,0.24)]" },
  { valor: "favorable", rotulo: "Favoráveis", cor: "bg-[#2D8A5F] dark:bg-[#3DA372]", ativo: "bg-[#2D8A5F] dark:bg-[#3DA372] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(45,138,95,0.24)]" },
  { valor: "unfavorable", rotulo: "Desfavoráveis", cor: "bg-[#C44040] dark:bg-[#D96B6B]", ativo: "bg-[#C44040] dark:bg-[#D96B6B] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(196,64,64,0.24)]" },
  { valor: "neutral", rotulo: "Neutras", cor: "bg-[#9A9AAA] dark:bg-[#7C7C88]", ativo: "bg-[#6A6A7A] dark:bg-[#9494A2] text-white dark:text-[#0E0E11]" },
];

/** Botão "pill" com dropdown — mesmo padrão de filtro usado pelo Jusbrasil (ex: "Em qualquer data ▾"). */
function DropdownPill({
  label,
  active,
  icon: Icone,
  children,
}: {
  label: string;
  active: boolean;
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = (returnFocus = false) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  useFecharAoClicarFora(ref, open, () => setOpen(false));

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
        style={{ fontSize: "13.4px", fontWeight: active ? 600 : 400 }}
      >
        {Icone && <Icone className={`w-3.5 h-3.5 ${active ? "" : "text-[#9090A8] dark:text-[#7C7C88]"}`} strokeWidth={1.8} />}
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
  const [filter, setFilter] = useState<"all" | Outcome>("all");
  const [sortBy, setSortBy] = useState<"relevance" | "date">("relevance");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [dateFrom, setDateFrom] = useState<string>(""); // yyyy-mm-dd
  const [dateTo, setDateTo] = useState<string>("");
  const [citacao, setCitacao] = useState<string | null>(null); // chip da "Base citada"
  const [tribunal, setTribunal] = useState<string | null>(null);
  const [recebida, setRecebida] = useState<{ chave: string; dados: ContagemFiltros | null } | null>(null);
  const restrito = estrutura !== null && temFiltroRestrito(estrutura);
  const chaveFiltro = JSON.stringify([estrutura?.dispositivos, estrutura?.expressoes, estrutura?.tribunais, estrutura?.fase]);
  useEffect(() => {
    if (!estrutura || !temFiltroRestrito(estrutura)) return;
    let vivo = true;
    contarFiltros(estrutura)
      .then((c) => vivo && setRecebida({ chave: chaveFiltro, dados: c }))
      .catch(() => vivo && setRecebida({ chave: chaveFiltro, dados: null })); // cabeçalho cai para o número de cards
    return () => {
      vivo = false;
    };
    // `chaveFiltro` resume dispositivos, expressões, tribunais e fase
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveFiltro]);
  // só vale a contagem do filtro atual (nunca a de um filtro anterior)
  const contagem = recebida?.chave === chaveFiltro ? recebida.dados : null;
  const contagemFalhou = recebida?.chave === chaveFiltro && recebida.dados === null;
  const contando = restrito && recebida?.chave !== chaveFiltro;

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
  const tribunais = useMemo(() => {
    const n = new Map<string, number>();
    for (const d of results) n.set(d.tribunal, (n.get(d.tribunal) ?? 0) + 1);
    return [...n].sort((a, b) => a[0].localeCompare(b[0], "pt-BR", { numeric: true }));
  }, [results]);
  const repetidas = useMemo(() => ementasRepetidas([...results].sort((a, b) => b.score_rrf - a.score_rrf)), [results]);
  const idsCitacao = useMemo(() => new Set(sintese?.base.find((b) => b.rotulo === citacao)?.ids ?? []), [sintese, citacao]);

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

  const periodLabel =
    dateFrom || dateTo
      ? `${dateFrom ? formatarData(dateFrom) : "…"} – ${dateTo ? formatarData(dateTo) : "…"}`
      : "Data";

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

  // desfecho, período e tribunal valem também para a faixa livre; o chip da base citada não (ele
  // vem das ementas da faixa restrita e esconderia toda a livre)
  const passaFiltrosComuns = (d: (typeof results)[number]) =>
    (filter === "all" || outcomeDe(d) === filter) && inPeriod(d.data_julgamento) && (!tribunal || d.tribunal === tribunal);

  const filteredResults = useMemo(
    () => sortedResults.filter((d) => passaFiltrosComuns(d) && (!citacao || idsCitacao.has(d.id))),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- passaFiltrosComuns só lê estes estados
    [sortedResults, filter, dateFrom, dateTo, tribunal, citacao, idsCitacao],
  );

  const contagemDesfecho = contarDesfechos(results);

  // Versões (V1, V2…) e "Refinar consulta": são da consulta, ficam no canto da faixa azul do resumo.
  const versaoAtual = versionNumero ?? versoes[versoes.length - 1]?.numero;
  const acoesConsulta = (
    <>
      {versoes.length > 1 && (
        <div role="tablist" aria-label="Versões da consulta" className="inline-flex p-[2px] gap-0.5 rounded-lg bg-white/10 border border-white/20">
          {versoes.map((v) => {
            const ativa = v.numero === versaoAtual;
            return (
              <button
                key={v.numero}
                role="tab"
                aria-selected={ativa}
                onClick={() => loadVersion(v)}
                title={v.numero === versoes.length ? "Versão mais recente" : `Versão ${v.numero}`}
                className={`px-2 py-[3px] rounded-md transition-colors ${ativa ? "bg-white text-[#1A3A5C]" : "text-[#AFC6E3] hover:text-white"}`}
                style={{ fontSize: "12px", fontWeight: ativa ? 600 : 400 }}
              >
                V{v.numero}
              </button>
            );
          })}
        </div>
      )}
      <button
        onClick={() => router.push("/revisao")}
        className="inline-flex items-center gap-1.5 rounded-lg bg-white text-[#1A3A5C] px-2.5 py-[5px] hover:bg-[#EEF3FB] transition-colors"
        style={{ fontSize: "12.8px", fontWeight: 600 }}
      >
        <SlidersHorizontal className="w-3.5 h-3.5" strokeWidth={1.8} />
        Refinar
      </button>
    </>
  );

  // Topo do resumo: quantas decisões, o que foi exigido e uma nota (corte em 20, contagem, vazio).
  const resumoTopo = useMemo(() => {
    const grupos: { verbo: string; itens: string[] }[] = [];
    if (restrito && estrutura) {
      const varias = (contagem?.total ?? results.length) !== 1;
      if (estrutura.dispositivos.length) {
        grupos.push({ verbo: varias ? "citam" : "cita", itens: contagem?.dispositivos.map((d) => d.rotulo) ?? estrutura.dispositivos });
      }
      if (estrutura.expressoes.length) grupos.push({ verbo: varias ? "contêm" : "contém", itens: estrutura.expressoes });
      if (estrutura.tribunais.length) grupos.push({ verbo: estrutura.tribunais.length > 1 ? "dos" : "do", itens: estrutura.tribunais.map(rotuloTribunal) });
      if (estrutura.fase) grupos.push({ verbo: "na fase de", itens: [ROTULO_FASE[estrutura.fase].toLowerCase()] });
    }
    if (!restrito) return { total: results.length, descricao: results.length === 1 ? "decisão encontrada" : "decisões encontradas", grupos, nota: null };
    if (results.length === 0) {
      return { total: 0, descricao: "decisões do acervo (≈70 mil acórdãos de 2025)", grupos, nota: "Abra a busca livre abaixo para ver decisões parecidas." };
    }
    if (!contagem) {
      return {
        total: results.length,
        descricao: results.length === 1 ? "decisão cumpre o filtro" : "decisões cumprem o filtro",
        grupos,
        nota: contagemFalhou ? "contagem do acervo indisponível" : contando ? "contando no acervo…" : null,
      };
    }
    return {
      total: contagem.total,
      descricao: contagem.total === 1 ? "decisão do acervo" : "decisões do acervo",
      grupos,
      nota: null,
    };
  }, [restrito, estrutura, contagem, contagemFalhou, contando, results]);

  // FA04 (RFC 3.2) — filtro de provimento aplicado mas com poucos resultados.
  const lowProvimentoResults = filter !== "all" && filteredResults.length > 0 && filteredResults.length < 3;

  // Exporta os resultados filtrados/ordenados como estão em tela — só formatação local, sem backend.
  const exportResults = () => {
    const lines = filteredResults.map((d, idx) =>
      [
        `${idx + 1}. ${titleFromEmenta(d.ementa)}`,
        `   ${d.tribunal} — ${d.turma} · ${formatarData(d.data_julgamento, "long")}`,
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
        <StepIndicator current={2} onEditarRevisao={() => router.push("/revisao")} />

        {estrutura && (
          <ParecerPesquisa
            key={`parecer|${versionNumero}|${JSON.stringify(estrutura)}`}
            estrutura={estrutura}
            filtro={
              restrito
                ? {
                    itens: [
                      ...(contagem?.dispositivos.map((d) => d.rotulo) ?? estrutura.dispositivos),
                      ...estrutura.expressoes,
                      ...estrutura.tribunais.map(rotuloTribunal),
                      ...(estrutura.fase ? [ROTULO_FASE[estrutura.fase]] : []),
                    ],
                    total: contagem?.total ?? null,
                  }
                : null
            }
            resposta={resposta}
            ordem={porRank}
            onIr={irPara}
            semResposta={restrito && results.length === 0 ? "Sem decisões no filtro restrito, a resposta não é gerada." : undefined}
          />
        )}

        {restrito && (
          <div className="w-full max-w-[800px] mb-3">
            <h2 className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "16.7px", fontWeight: 600 }}>
              Filtro restrito
            </h2>
            <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>
              Só entram decisões que citam todos os dispositivos e contêm todas as expressões informados.
            </p>
          </div>
        )}

        {/* Resumo das decisões: total, termos exigidos, desfechos, panorama, base citada, para citar */}
        <ResumoDecisoes
          total={resumoTopo.total}
          descricao={resumoTopo.descricao}
          grupos={resumoTopo.grupos}
          nota={resumoTopo.nota}
          tese={estrutura?.tese_central ? truncate(estrutura.tese_central, 180) : ""}
          desfechos={contagemDesfecho}
          mostradas={results.length}
          sintese={sintese}
          citacao={citacao}
          onCitacao={setCitacao}
          acoes={acoesConsulta}
        />

        {/* Barra de filtros: desfecho (segmentos), tribunal, data e ordem; versões e refinar à direita */}
        <div className="w-full max-w-[800px] mb-5 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none px-3.5 py-3 flex flex-wrap items-center gap-x-3 gap-y-2.5">
          <div role="group" aria-label="Filtrar por desfecho" className="inline-flex p-[3px] gap-0.5 rounded-[10px] border border-[#E0E0EA] dark:border-[#2A2A32] bg-[#FAFAFC] dark:bg-[#1C1C21]">
            {SEGMENTOS.map((sgm) => {
              const n = sgm.valor === "all" ? results.length : contagemDesfecho[sgm.valor];
              const ativo = filter === sgm.valor;
              return (
                <button
                  key={sgm.valor}
                  onClick={() => setFilter(sgm.valor)}
                  aria-pressed={ativo}
                  className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-[7px] transition-all ${ativo ? sgm.ativo : "text-[#6B6B80] dark:text-[#A6A6B4] hover:bg-white dark:hover:bg-[#17171B]"}`}
                  style={{ fontSize: "13.4px", fontWeight: ativo ? 600 : 400 }}
                >
                  {sgm.cor && <span className={`w-[7px] h-[7px] rounded-full ${ativo ? "bg-white/90" : sgm.cor}`} />}
                  <span className={sgm.valor === "all" ? "" : "hidden sm:inline"}>{sgm.rotulo}</span>
                  <span className="tabular-nums opacity-80" style={{ fontSize: "12px" }}>{n}</span>
                </button>
              );
            })}
          </div>

          <span className="flex-1" />

            <DropdownPill icon={Scale} label={tribunal ?? "Tribunal"} active={tribunal !== null}>
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

            <DropdownPill icon={Calendar} label={periodLabel} active={dateFrom !== "" || dateTo !== ""}>
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

            <DropdownPill icon={TrendingUp} label={sortBy === "relevance" ? "Relevância" : "Data"} active={false}>
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
        {filteredResults.length === 0 && restrito && results.length === 0 ? null : filteredResults.length === 0 ? (
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
            {filteredResults.map((decision) => (
              <ResultadoCard
                key={decision.id}
                decision={decision}
                estrutura={estrutura}
                rank={ranks.get(decision.id)}
                total={results.length}
                ementaIgualA={repetidas.has(decision.id) ? ranks.get(repetidas.get(decision.id)!) : undefined}
              />
            ))}

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

        {estrutura && restrito && (
          <FaixaLivre key={`faixa-livre|${versionNumero}|${JSON.stringify(estrutura)}`} estrutura={estrutura} excluir={new Set(results.map((d) => d.id))} passa={passaFiltrosComuns} />
        )}
        {!restrito && (
          <p className="w-full max-w-[800px] mt-6 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
            Sem filtro restrito: a busca semântica e a por termos olharam o acervo inteiro. Para restringir, informe normas, expressões, tribunal ou fase na Revisão de Contexto.
          </p>
        )}
      </div>
    </main>
  );
}
