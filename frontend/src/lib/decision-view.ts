import type { EstruturaArgumentativa, ResultCard, TipoDocumento } from "@/lib/api";

/** O schema real não tem um campo de "título" — a ementa é o único texto de manchete
 *  disponível. Usa a primeira frase como título do card/detalhe. */
export function titleFromEmenta(ementa: string): string {
  const trimmed = ementa.trim();
  if (!trimmed) return "Decisão sem ementa disponível";
  const firstSentence = trimmed.split(/(?<=[.!?])\s/)[0] ?? trimmed;
  return firstSentence.length > 140 ? `${firstSentence.slice(0, 140).trimEnd()}…` : firstSentence;
}

export function truncate(text: string, max: number): string {
  const trimmed = text.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max).trimEnd()}…` : trimmed;
}

/** "Entidades correspondentes": termos do contexto pesquisado (normas/agentes/violações) que
 *  aparecem literalmente no texto do documento. A API não devolve spans/highlights, então esta
 *  é a única checagem honesta possível no cliente — sem inventar uma correspondência que o
 *  backend não calculou. */
export function matchedEntities(estrutura: EstruturaArgumentativa | null, texto: string): string[] {
  if (!estrutura) return [];
  const haystack = texto.toLowerCase();
  const candidatos = [...estrutura.normas, ...estrutura.agente_nocivo, ...estrutura.violacoes];
  const vistos = new Set<string>();
  return candidatos.filter((termo) => {
    const t = termo.trim();
    if (!t || vistos.has(t.toLowerCase())) return false;
    if (!haystack.includes(t.toLowerCase())) return false;
    vistos.add(t.toLowerCase());
    return true;
  });
}

/** O score do RRF (query/search/hybrid_search.py) não tem escala absoluta interpretável como
 *  "% de relevância" — normaliza relativo ao maior score do próprio conjunto de resultados. */
export function relevancePercent(score: number, maxScore: number): number {
  if (maxScore <= 0) return 0;
  return Math.round((score / maxScore) * 100);
}

/** Mesmo comparador de query/search/categorical_sort.py::ordenar — hierarquia jurídica primeiro
 *  (súmula > OJ > precedente > acórdão), relevância/data como critério secundário. Replicado no
 *  cliente para reordenar o mesmo lote de resultados sem precisar chamar a API de novo. */
export function compareResultCards(a: ResultCard, b: ResultCard, por: "relevancia" | "data"): number {
  if (a.hierarquia_categoria !== b.hierarquia_categoria) {
    return a.hierarquia_categoria - b.hierarquia_categoria;
  }
  if (por === "data") {
    const da = a.data_julgamento ? Date.parse(a.data_julgamento) : -Infinity;
    const db = b.data_julgamento ? Date.parse(b.data_julgamento) : -Infinity;
    return db - da;
  }
  return b.score_rrf - a.score_rrf;
}

export const TIPO_DOCUMENTO_LABEL: Record<TipoDocumento, string> = {
  ACORDAO: "Acórdão",
  SUMULA: "Súmula",
  OJ: "Orientação Jurisprudencial",
  PRECEDENTE: "Precedente",
};
