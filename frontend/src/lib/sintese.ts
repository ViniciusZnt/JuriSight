import type { PosicaoTese, ResultCard } from "@/lib/api";
import { contarDesfechos, outcomeDe } from "@/lib/provimento";

type Item = Parameters<typeof outcomeDe>[0] & Pick<ResultCard, "id" | "ementa" | "score_rrf">;

export const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

const SDI: Record<string, string> = { "1": "1", I: "1", "2": "2", II: "2" };

/** Normas e precedentes citados no texto, por regex simples (sem LLM): Súmula, OJ, art. da CLT,
 *  NR, Tema e ARE/RE do STF. Rótulos normalizados para contar a mesma citação escrita de jeitos
 *  diferentes ("SÚMULA Nº 289 DO C. TST" e "Súmula 289/TST" viram "Súmula 289 do TST"). */
const PADROES: [RegExp, (m: RegExpMatchArray) => string[]][] = [
  [
    /\bs[úu]mula\s+(?:n[º°o.]*\s*)?(\d{1,3})(?:\s*,\s*[IVX]{1,4}\b)?(?:\s*,?\s*(?:d[oa]\s+(?:c\.\s*|e\.\s*)?|\/\s*)(TST|STF|STJ))?/gi,
    (m) => [`Súmula ${+m[1]}${m[2] ? ` do ${m[2].toUpperCase()}` : ""}`],
  ],
  [
    /\b(?:OJ|orienta[çc][ãa]o\s+jurisprudencial)\s+(?:n[º°o.]*\s*)?(\d{1,3})(?:\s*,?\s*(?:da\s+)?S\.?B?\.?D\.?I\.?\s*[-–]?\s*(1|2|II|I)\b)?/gi,
    (m) => [`OJ ${+m[1]}${m[2] ? ` da SDI-${SDI[m[2].toUpperCase()]}` : ""}`],
  ],
  [
    /\barts?\.?\s*(\d{1,3}(?:-[A-Z])?[º°o]?(?:\s*(?:,|e)\s*\d{1,3}(?:-[A-Z])?[º°o]?)*)\s*,?\s*(?:(?:§|par[áa]grafo|inciso|caput|[IVX]{1,4}\b)[^,;]{0,15},?\s*)*da\s+(?:CLT|consolida[çc][ãa]o\s+das\s+leis\s+do\s+trabalho)/gi,
    (m) => (m[1].match(/\d+(?:-[A-Z])?/gi) ?? []).map((n) => `art. ${n.toUpperCase()} da CLT`),
  ],
  [/\b(?:NR|norma\s+regulamentadora)\s*(?:n[º°o.]*\s*)?[-–]?\s*(\d{1,2})\b/gi, (m) => [`NR-${+m[1]}`]],
  [/\btema\s+(?:repetitivo\s+|de\s+repercuss[ãa]o\s+geral\s+)?(?:n[º°o.]*\s*)?(\d{1,4})\b/gi, (m) => [`Tema ${+m[1]}`]],
  [/\b(ARE|RE)\s+(?:n[º°o.]*\s*)?(\d{3}\.?\d{3})\b/g, (m) => [`${m[1]} ${m[2].replace(/^(\d{3})\.?(\d{3})$/, "$1.$2")}`]],
];

export function citacoesDe(texto: string): string[] {
  const achadas = new Set<string>();
  for (const [re, rotulos] of PADROES) for (const m of texto.matchAll(re)) rotulos(m).forEach((r) => achadas.add(r));
  return [...achadas];
}

export interface Sintese {
  abertura: string;
  tendencia: string;
  /** Normas/precedentes citados em 2 ou mais ementas, com os ids das decisões que os citam. */
  base: { rotulo: string; ids: string[] }[];
  /** Até 2 decisões mais relevantes de cada lado. Com a posição lida pela resposta gerada, os lados
   *  são os dela (deferiu / negou / negou com outros fatos), para o painel citar as mesmas decisões. */
  trabalhador: string[];
  empresa: string[];
  outrosFatos: string[];
  porResposta: boolean;
}

/** Resposta-síntese do topo de /resultados: só o que os próprios resultados mostram (mesma regra
 *  e mesmo corte de confiança do selo), sem inventar nada. */
export function sintetizar(resultados: Item[], posicoes?: Map<string, PosicaoTese> | null): Sintese | null {
  const n = resultados.length;
  if (n === 0) return null;
  const { favorable: f, unfavorable: e, neutral: z } = contarDesfechos(resultados);
  const abertura =
    f >= 0.6 * n && f >= 2 * e
      ? "A maioria das decisões encontradas favorece o trabalhador."
      : e >= 0.6 * n && e >= 2 * f
        ? "A maioria das decisões encontradas favorece a empresa."
        : z >= 0.6 * n
          ? "A maioria das decisões não tem um lado claro na classificação automática."
          : "As decisões se dividem.";
  const tendencia = `${n === 1 ? "Da única decisão" : `Das ${n} decisões`}, ${plural(f, "favorece", "favorecem")} o trabalhador, ${e} a empresa e ${z} sem lado claro.`;

  const porCitacao = new Map<string, string[]>();
  for (const d of resultados) for (const c of citacoesDe(d.ementa)) porCitacao.set(c, [...(porCitacao.get(c) ?? []), d.id]);
  const base = [...porCitacao]
    .map(([rotulo, ids]) => ({ rotulo, ids }))
    .filter((b) => b.ids.length > 1) // citado por uma só decisão é ruído (ex.: art. 461 num pedido de equiparação)
    .sort((a, b) => b.ids.length - a.ids.length || a.rotulo.localeCompare(b.rotulo, "pt-BR", { numeric: true }))
    .slice(0, 8);

  const porRelevancia = [...resultados].sort((a, b) => b.score_rrf - a.score_rrf);
  const lado = (o: string, p: PosicaoTese) =>
    porRelevancia.filter((d) => (posicoes ? posicoes.get(d.id) === p : outcomeDe(d) === o)).slice(0, 2).map((d) => d.id);
  return {
    abertura,
    tendencia,
    base,
    trabalhador: lado("favorable", "deferiu"),
    empresa: lado("unfavorable", "negou"),
    outrosFatos: posicoes ? lado("", "fato_diferente") : [],
    porResposta: !!posicoes,
  };
}
