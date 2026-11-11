import { ArrowRight, BookOpen, Info, PieChart, Quote, Scale } from "lucide-react";
import type { ResultCard } from "@/lib/api";
import type { Outcome } from "@/lib/outcome";
import { formatarData } from "@/lib/decision-view";
import type { Sintese } from "@/lib/sintese";

type Desfechos = Record<Outcome, number>;

interface Props {
  /** Número em destaque no topo (decisões do acervo que cumprem o filtro, ou encontradas). */
  total: number;
  /** O que vem depois do número: "decisões do acervo", "decisões encontradas"… */
  descricao: string;
  /** Termos exigidos, agrupados pelo verbo ("citam" dispositivos, "contêm" expressões). */
  grupos: { verbo: string; itens: string[] }[];
  /** Linha discreta sob o título ("mostrando as 20 mais relevantes", "contando no acervo…"). */
  nota: string | null;
  tese: string;
  desfechos: Desfechos;
  /** Quantas decisões estão na lista (base da porcentagem do panorama). */
  mostradas: number;
  filtro: "all" | Outcome;
  onFiltro: (f: "all" | Outcome) => void;
  sintese: Sintese | null;
  porId: Map<string, ResultCard>;
  ranks: Map<string, number>;
  citacao: string | null;
  onCitacao: (rotulo: string | null) => void;
  onIr: (id: string) => void;
}

const PLACAS: { valor: Outcome; um: string; varios: string; cls: string; ativo: string }[] = [
  {
    valor: "favorable", um: "favorável", varios: "favoráveis",
    cls: "bg-[#2D8A5F] dark:bg-[#3DA372] text-white dark:text-[#0E0E11] border-transparent shadow-[0_1px_6px_rgba(0,0,0,0.12)]",
    ativo: "ring-2 ring-offset-2 ring-[#2D8A5F] dark:ring-[#3DA372] ring-offset-[#F2F6FC] dark:ring-offset-[#131C28]",
  },
  {
    valor: "unfavorable", um: "desfavorável", varios: "desfavoráveis",
    cls: "bg-[#C44040] dark:bg-[#D96B6B] text-white dark:text-[#0E0E11] border-transparent shadow-[0_1px_6px_rgba(0,0,0,0.12)]",
    ativo: "ring-2 ring-offset-2 ring-[#C44040] dark:ring-[#D96B6B] ring-offset-[#F2F6FC] dark:ring-offset-[#131C28]",
  },
  {
    valor: "neutral", um: "neutra", varios: "neutras",
    cls: "bg-white dark:bg-[#17171B] text-[#4A4A5A] dark:text-[#C4C4CE] border-[#E0E0EA] dark:border-[#2A2A32]",
    ativo: "ring-2 ring-offset-2 ring-[#6A6A7A] dark:ring-[#9494A2] ring-offset-[#F2F6FC] dark:ring-offset-[#131C28]",
  },
];

const ROTULO_COLUNA = "text-[#4A4A5A] dark:text-[#C4C4CE] uppercase tracking-[0.05em]";

function CabecalhoColuna({ icone: Icone, titulo }: { icone: typeof Scale; titulo: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="flex items-center justify-center w-[26px] h-[26px] rounded-lg bg-[#EFF4FA] dark:bg-[#1A2A3C] text-[#1A3A5C] dark:text-[#8AB0DC]">
        <Icone className="w-3.5 h-3.5" strokeWidth={1.8} />
      </span>
      <span className={ROTULO_COLUNA} style={{ fontSize: "11.5px", fontWeight: 700 }}>{titulo}</span>
    </div>
  );
}

const pct = (n: number, de: number) => (de ? Math.round((100 * n) / de) : 0);

/** Resumo das decisões no topo da lista: faixa azul com o total, os termos exigidos e a tese;
 *  placas de desfecho (que filtram a lista); panorama, base citada (que filtra pelos que a citam)
 *  e precedentes para citar (que levam ao card). */
export function ResumoDecisoes({
  total, descricao, grupos, nota, tese, desfechos, mostradas, filtro, onFiltro,
  sintese, porId, ranks, citacao, onCitacao, onIr,
}: Props) {
  const maxBase = Math.max(1, ...(sintese?.base.map((b) => b.ids.length) ?? [1]));
  const lados = sintese
    ? [
        { titulo: "Favorável ao trabalhador", ids: sintese.trabalhador, cls: "bg-[#2D8A5F] dark:bg-[#3DA372]" },
        { titulo: "Favorável à empresa", ids: sintese.empresa, cls: "bg-[#C44040] dark:bg-[#D96B6B]" },
      ].filter((l) => l.ids.length > 0)
    : [];

  return (
    <section aria-label="Resumo das decisões" className="w-full max-w-[800px] mb-6 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none overflow-hidden">
      {/* Topo: total, termos exigidos e tese */}
      <div className="flex gap-3.5 items-start px-5 sm:px-6 pt-5 pb-4 bg-[#1A3A5C] dark:bg-[#132A44]">
        <div className="flex items-center justify-center w-[42px] h-[42px] rounded-xl bg-white text-[#1A3A5C] flex-shrink-0">
          <Scale className="w-5 h-5" strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[#AFC6E3] uppercase tracking-[0.07em]" style={{ fontSize: "11px", fontWeight: 700 }}>
            Resumo das decisões
          </p>
          <p className="text-[#D6E3F3] mt-0.5" style={{ fontSize: "15px", fontWeight: 600 }}>
            <span className="text-white tabular-nums mr-1" style={{ fontSize: "22px", fontWeight: 700 }}>
              {total.toLocaleString("pt-BR")}
            </span>
            {descricao}
          </p>
          {grupos.map((g) => (
            <div key={g.verbo} className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-[#AFC6E3]" style={{ fontSize: "14px" }}>{g.verbo}</span>
              {g.itens.map((t, i) => (
                <span key={t} className="contents">
                  {i > 0 && <span className="text-[#AFC6E3]" style={{ fontSize: "14px" }}>e</span>}
                  <span className="bg-white text-[#1A3A5C] rounded-[9px] px-3 py-1 shadow-[0_2px_8px_rgba(0,0,0,0.18)]" style={{ fontSize: "17px", fontWeight: 700 }}>
                    {t}
                  </span>
                </span>
              ))}
            </div>
          ))}
          {nota && (
            <p className="text-[#AFC6E3] mt-2" style={{ fontSize: "13px" }}>{nota}</p>
          )}
          {tese && (
            <p className="mt-3 pl-2.5 border-l-[3px] border-white/35 text-[#E3ECF7] leading-relaxed" style={{ fontSize: "13.6px" }}>
              <span className="text-[#AFC6E3]">Tese:</span> {tese}
            </p>
          )}
        </div>
      </div>

      {sintese && (
        <>
          {/* Placas de desfecho: filtram a lista */}
          <div className="flex flex-wrap items-center gap-2 px-5 sm:px-6 py-3.5 bg-[#F2F6FC] dark:bg-[#131C28] border-b border-[#E1E8F3] dark:border-[#26313F]">
            {PLACAS.map((p) => {
              const n = desfechos[p.valor];
              const ativo = filtro === p.valor;
              return (
                <button
                  key={p.valor}
                  onClick={() => onFiltro(ativo ? "all" : p.valor)}
                  aria-pressed={ativo}
                  className={`inline-flex items-baseline gap-1.5 rounded-[10px] border px-3.5 py-1.5 transition-all hover:brightness-105 ${p.cls} ${ativo ? p.ativo : ""}`}
                >
                  <span className="tabular-nums" style={{ fontSize: "20px", fontWeight: 700, lineHeight: 1 }}>{n}</span>
                  <span style={{ fontSize: "13.6px", fontWeight: 600 }}>{n === 1 ? p.um : p.varios}</span>
                </button>
              );
            })}
            <span className="text-[#8A8A9A] dark:text-[#9494A2] ml-1" style={{ fontSize: "12.4px" }}>
              {`das ${mostradas} mais relevantes · clique para filtrar`}
            </span>
          </div>

          {/* Panorama · Base citada · Para citar */}
          <div className="grid grid-cols-1 md:grid-cols-[1.25fr_1fr_1fr]">
            <div className="px-5 py-4 min-w-0">
              <CabecalhoColuna icone={PieChart} titulo="Panorama" />
              <div className="flex h-2 rounded-full overflow-hidden bg-[#F2F2F6] dark:bg-[#26262C] mb-2">
                <div className="bg-[#2D8A5F] dark:bg-[#3DA372]" style={{ width: `${pct(desfechos.favorable, mostradas)}%` }} />
                <div className="bg-[#C44040] dark:bg-[#D96B6B]" style={{ width: `${pct(desfechos.unfavorable, mostradas)}%` }} />
              </div>
              <div className="flex justify-between text-[#8A8A9A] dark:text-[#9494A2] mb-3" style={{ fontSize: "11.6px" }}>
                <span>trabalhador {pct(desfechos.favorable, mostradas)}%</span>
                <span>empresa {pct(desfechos.unfavorable, mostradas)}%</span>
                <span>sem lado {pct(desfechos.neutral, mostradas)}%</span>
              </div>
              <span className="inline-flex rounded-full border border-[#C8D9EF] dark:border-[#2A3A4C] bg-[#EEF3FB] dark:bg-[#1A2A3C] text-[#1A3A5C] dark:text-[#8AB0DC] px-2.5 py-0.5 mb-2" style={{ fontSize: "12.4px", fontWeight: 700 }}>
                {sintese.abertura.replace(/\.$/, "")}
              </span>
              <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed" style={{ fontSize: "14px" }}>{sintese.tendencia}</p>
            </div>

            <div className="px-5 py-4 min-w-0 border-t md:border-t-0 md:border-l border-[#F0F0F6] dark:border-[#26262C]">
              <CabecalhoColuna icone={BookOpen} titulo="Base citada" />
              {sintese.base.length === 0 ? (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>Nenhuma norma citada em mais de uma ementa.</p>
              ) : (
                <ul className="-mx-2">
                  {sintese.base.slice(0, 5).map(({ rotulo, ids }) => {
                    const ativo = citacao === rotulo;
                    return (
                      <li key={rotulo}>
                        <button
                          onClick={() => onCitacao(ativo ? null : rotulo)}
                          aria-pressed={ativo}
                          title={ativo ? "Mostrar todas as decisões" : `Mostrar só as decisões que citam ${rotulo}`}
                          className={`w-full grid grid-cols-[minmax(0,1fr)_auto] gap-2 items-center rounded-lg px-2 py-1.5 text-left transition-colors ${
                            ativo ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] text-white dark:text-[#0E0E11]" : "text-[#0F1117] dark:text-[#ECECEF] hover:bg-[#F5F8FD] dark:hover:bg-[#1A2A3C]"
                          }`}
                        >
                          <span className="min-w-0" style={{ fontSize: "13.4px" }}>
                            {rotulo}
                            <span className={`block h-[3px] rounded-full mt-1 ${ativo ? "bg-white/30" : "bg-[#C8D9EF] dark:bg-[#2A3A4C]"}`}>
                              <span className={`block h-full rounded-full ${ativo ? "bg-white" : "bg-[#1A3A5C] dark:bg-[#8AB0DC]"}`} style={{ width: `${(100 * ids.length) / maxBase}%` }} />
                            </span>
                          </span>
                          <span
                            className={`min-w-[24px] text-center rounded-md border px-1.5 tabular-nums ${
                              ativo ? "border-white/40 text-white dark:text-[#0E0E11]" : "border-[#C8D9EF] dark:border-[#2A3A4C] bg-[#EEF3FB] dark:bg-[#1A2A3C] text-[#1A3A5C] dark:text-[#8AB0DC]"
                            }`}
                            style={{ fontSize: "11.8px", fontWeight: 700 }}
                            aria-label={`em ${ids.length} decisões`}
                          >
                            {ids.length}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="px-5 py-4 min-w-0 border-t md:border-t-0 md:border-l border-[#F0F0F6] dark:border-[#26262C]">
              <CabecalhoColuna icone={Quote} titulo="Para citar" />
              {lados.length === 0 && (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>Nenhuma decisão com lado claro.</p>
              )}
              {lados.map((l, i) => (
                <div key={l.titulo} className={i > 0 ? "mt-3" : ""}>
                  <span className={`inline-flex rounded-md px-2 py-0.5 text-white dark:text-[#0E0E11] uppercase tracking-[0.05em] ${l.cls}`} style={{ fontSize: "11px", fontWeight: 700 }}>
                    {l.titulo}
                  </span>
                  <ul className="-mx-2 mt-1">
                    {l.ids.map((id) => {
                      const d = porId.get(id);
                      return (
                        <li key={id}>
                          <a
                            href={`#decisao-${id}`}
                            onClick={() => onIr(id)}
                            className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-2.5 items-center rounded-lg px-2 py-1.5 hover:bg-[#F5F8FD] dark:hover:bg-[#1A2A3C] transition-colors"
                          >
                            <span className="min-w-[32px] h-[26px] grid place-items-center rounded-md border border-[#E1E8F3] dark:border-[#26313F] bg-[#F5F8FD] dark:bg-[#131C28] text-[#1A3A5C] dark:text-[#8AB0DC] tabular-nums" style={{ fontSize: "12.2px", fontWeight: 700 }}>
                              #{ranks.get(id)}
                            </span>
                            <span className="min-w-0 text-[#0F1117] dark:text-[#ECECEF] leading-tight" style={{ fontSize: "13.2px" }}>
                              {d?.tribunal} · {d?.turma}
                              {d?.data_julgamento && (
                                <span className="block text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "11.6px" }}>
                                  {formatarData(d.data_julgamento, "short")}
                                </span>
                              )}
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-[#9090A8] dark:text-[#7C7C88]" strokeWidth={1.8} />
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <p className="flex items-start gap-1.5 px-5 sm:px-6 py-2.5 border-t border-[#F0F0F6] dark:border-[#26262C] text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.2px" }}>
            <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" strokeWidth={1.8} />
            Lado e citações vêm de classificação automática das ementas e podem conter erros. Confira a decisão antes de citar.
          </p>
        </>
      )}
    </section>
  );
}
