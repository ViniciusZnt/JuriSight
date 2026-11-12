import { BookOpen, Info, PieChart, Scale } from "lucide-react";
import type { Outcome } from "@/lib/outcome";
import type { Sintese } from "@/lib/sintese";

type Desfechos = Record<Outcome, number>;

interface Props {
  /** Número em destaque (decisões do acervo que cumprem o filtro, ou encontradas). */
  total: number;
  /** O que vem depois do número: "decisões do acervo", "decisões encontradas"… */
  descricao: string;
  /** Termos exigidos, agrupados pelo verbo ("citam" dispositivos, "contêm" expressões). */
  grupos: { verbo: string; itens: string[] }[];
  /** Linha discreta sob o título ("contando no acervo…", aviso de faixa vazia). */
  nota: string | null;
  tese: string;
  desfechos: Desfechos;
  /** Quantas decisões estão na lista (base do panorama). */
  mostradas: number;
  sintese: Sintese | null;
  citacao: string | null;
  onCitacao: (rotulo: string | null) => void;
  /** Controles da consulta (versões, refinar), no canto da faixa azul. */
  acoes?: React.ReactNode;
}

const ROTULO = "flex items-center gap-1.5 mb-2 text-[#8A8A9A] dark:text-[#9494A2] uppercase tracking-[0.06em]";
const pct = (n: number, de: number) => (de ? (100 * n) / de : 0);

/** Resumo das decisões no topo da lista: faixa azul com o total, os termos exigidos, a tese e os
 *  controles da consulta; embaixo, o panorama dos desfechos e a base citada (que filtra a lista
 *  pelos cards que citam cada norma). O filtro por desfecho fica na barra de filtros. */
export function ResumoDecisoes({ total, descricao, grupos, nota, tese, desfechos, mostradas, sintese, citacao, onCitacao, acoes }: Props) {
  return (
    <section aria-label="Resumo das decisões" className="w-full max-w-[800px] mb-4 bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none overflow-hidden">
      {/* Faixa azul: total, termos exigidos, tese e controles da consulta */}
      <div className="grid grid-cols-[auto_minmax(0,1fr)] sm:grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3.5 gap-y-3 items-start px-5 pt-4 pb-3.5 bg-[#1A3A5C] dark:bg-[#132A44]">
        <div className="flex items-center justify-center w-[38px] h-[38px] rounded-[10px] bg-white text-[#1A3A5C] flex-shrink-0">
          <Scale className="w-[19px] h-[19px]" strokeWidth={1.8} />
        </div>
        <div className="min-w-0">
          <p className="text-[#D6E3F3] leading-[1.9]" style={{ fontSize: "15px", fontWeight: 500 }}>
            <span className="text-white tabular-nums mr-1" style={{ fontSize: "20px", fontWeight: 700 }}>
              {total.toLocaleString("pt-BR")}
            </span>
            {descricao}
            {grupos.map((g) => (
              <span key={g.verbo}>
                {" "}{g.verbo}{" "}
                {g.itens.map((t, i) => (
                  <span key={t}>
                    {i > 0 && " e "}
                    <span className="inline-block bg-white text-[#1A3A5C] rounded-lg px-2.5 mx-0.5 leading-normal shadow-[0_1px_4px_rgba(0,0,0,0.18)]" style={{ fontSize: "14.5px", fontWeight: 700 }}>
                      {t}
                    </span>
                  </span>
                ))}
              </span>
            ))}
          </p>
          {nota && <p className="text-[#AFC6E3]" style={{ fontSize: "12.8px" }}>{nota}</p>}
          {tese && (
            <p className="mt-1.5 text-[#C9D8EA] leading-relaxed line-clamp-2" style={{ fontSize: "13px" }} title={tese}>
              <span className="text-[#AFC6E3]">Tese:</span> {tese}
            </p>
          )}
        </div>
        {acoes && <div className="col-span-2 sm:col-span-1 flex items-center gap-1.5">{acoes}</div>}
      </div>

      {sintese && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2">
            <div className="px-5 py-3.5 min-w-0">
              <p className={ROTULO} style={{ fontSize: "11px", fontWeight: 700 }}>
                <PieChart className="w-3.5 h-3.5" strokeWidth={1.8} />
                {mostradas === 1 ? "Panorama da decisão mais relevante" : `Panorama das ${mostradas} mais relevantes`}
              </p>
              <div className="flex h-2 rounded-full overflow-hidden bg-[#EEEEF3] dark:bg-[#26262C] mb-2.5" aria-hidden>
                <div className="bg-[#2D8A5F] dark:bg-[#3DA372]" style={{ width: `${pct(desfechos.favorable, mostradas)}%` }} />
                <div className="bg-[#C44040] dark:bg-[#D96B6B]" style={{ width: `${pct(desfechos.unfavorable, mostradas)}%` }} />
              </div>
              <p className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "15px", fontWeight: 700 }}>
                {sintese.abertura.replace(/\.$/, "")}
              </p>
              <p className="text-[#4A4A5A] dark:text-[#C4C4CE] leading-relaxed" style={{ fontSize: "13.6px" }}>
                <b className="text-[#2D8A5F] dark:text-[#3DA372]">{desfechos.favorable}</b>
                {desfechos.favorable === 1 ? " favorece" : " favorecem"} o trabalhador,{" "}
                <b className="text-[#C44040] dark:text-[#D96B6B]">{desfechos.unfavorable}</b> a empresa,{" "}
                <b className="text-[#0F1117] dark:text-[#ECECEF]">{desfechos.neutral}</b> sem lado claro.
              </p>
            </div>

            <div className="px-5 py-3.5 min-w-0 border-t sm:border-t-0 sm:border-l border-[#F0F0F6] dark:border-[#26262C]">
              <p className={ROTULO} style={{ fontSize: "11px", fontWeight: 700 }}>
                <BookOpen className="w-3.5 h-3.5" strokeWidth={1.8} />
                Base citada
              </p>
              {sintese.base.length === 0 ? (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>Nenhuma norma citada em mais de uma ementa.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {sintese.base.slice(0, 6).map(({ rotulo, ids }) => {
                    const ativo = citacao === rotulo;
                    return (
                      <button
                        key={rotulo}
                        onClick={() => onCitacao(ativo ? null : rotulo)}
                        aria-pressed={ativo}
                        title={ativo ? "Mostrar todas as decisões" : `Mostrar só as decisões que citam ${rotulo}`}
                        className={`inline-flex items-center gap-1.5 rounded-lg border pl-2.5 pr-1 py-[3px] transition-colors ${
                          ativo
                            ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] border-[#1A3A5C] dark:border-[#8AB0DC] text-white dark:text-[#0E0E11]"
                            : "bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC] hover:border-[#1A3A5C] dark:hover:border-[#8AB0DC]"
                        }`}
                        style={{ fontSize: "13px" }}
                      >
                        {rotulo}
                        <span
                          className={`min-w-[20px] text-center rounded-md px-1.5 tabular-nums ${
                            ativo ? "bg-white text-[#1A3A5C]" : "bg-[#1A3A5C] dark:bg-[#8AB0DC] text-white dark:text-[#0E0E11]"
                          }`}
                          style={{ fontSize: "11.4px", fontWeight: 700 }}
                          aria-label={`em ${ids.length} decisões`}
                        >
                          {ids.length}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <p className="flex items-center gap-1.5 px-5 py-2 border-t border-[#F0F0F6] dark:border-[#26262C] text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "11.8px" }}>
            <Info className="w-3 h-3 flex-shrink-0" strokeWidth={1.8} />
            Lado e citações vêm de classificação automática das ementas. Confira antes de citar.
          </p>
        </>
      )}
    </section>
  );
}
