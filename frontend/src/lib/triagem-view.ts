/** Como a tela de resultados arruma os cards pela nota da triagem por IA (POST /triagem). */
import type { Avaliacao, NotaTriagem, ResultCard } from "@/lib/api";

/** A escala do conjunto-ouro, em palavras de advogado (selo do card). */
export const ROTULO_NOTA: Record<NotaTriagem, string> = {
  3: "Mesmo problema e fato",
  2: "Mesmo pedido",
  1: "Mesmo ramo",
  0: "Outro tema",
};

/** Máximo de decisões que vão à resposta gerada (POST /resposta). */
export const MAX_RESPOSTA = 25;

export interface Secoes {
  relacionadas: ResultCard[];
  naoAvaliadas: ResultCard[];
  poucoRelacionadas: ResultCard[];
  /** Sem ementa: a IA não tem o que ler, então não recebem nota. */
  semEmenta: ResultCard[];
}

/** Separa os resultados (na ordem do RRF) em três seções:
 *  - relacionadas: nota 3, depois 2 (empate na ordem do RRF), e por fim as que o advogado marcou
 *    "É relevante", na ordem do voto;
 *  - não avaliadas: na ordem do RRF;
 *  - pouco relacionadas: nota 1, depois 0. */
export function organizar(
  resultados: ResultCard[],
  avaliacoes: Map<string, Avaliacao>,
  relevantesUsuario: string[],
  semEmenta: Set<string> = new Set(),
): Secoes {
  const votadas = new Set(relevantesUsuario);
  const porNota = (a: ResultCard, b: ResultCard) => avaliacoes.get(b.id)!.nota - avaliacoes.get(a.id)!.nota;
  const avaliadas = resultados.filter((d) => avaliacoes.has(d.id) && !votadas.has(d.id));
  const porId = new Map(resultados.map((d) => [d.id, d]));
  return {
    relacionadas: [
      ...avaliadas.filter((d) => avaliacoes.get(d.id)!.nota >= 2).sort(porNota),
      ...relevantesUsuario.flatMap((id) => porId.get(id) ?? []),
    ],
    naoAvaliadas: resultados.filter((d) => !avaliacoes.has(d.id) && !votadas.has(d.id) && !semEmenta.has(d.id)),
    poucoRelacionadas: avaliadas.filter((d) => avaliacoes.get(d.id)!.nota < 2).sort(porNota),
    semEmenta: resultados.filter((d) => semEmenta.has(d.id) && !avaliacoes.has(d.id) && !votadas.has(d.id)),
  };
}

/** #1..#N na ordem relacionadas → não avaliadas → pouco relacionadas → sem ementa (a que a resposta cita).
 *  `prefixo` (as decisões de uma resposta já salva) vem primeiro, na ordem dela: reabrir uma
 *  conversa mantém os #N que a resposta cita, mesmo que a triagem tenha avaliado mais depois. */
export function numeracao(s: Secoes, prefixo: string[] = []): Map<string, number> {
  const todas = [...s.relacionadas, ...s.naoAvaliadas, ...s.poucoRelacionadas, ...s.semEmenta];
  const presentes = new Set(todas.map((d) => d.id));
  const primeiro = prefixo.filter((id) => presentes.has(id));
  const fixos = new Set(primeiro);
  return new Map([...primeiro, ...todas.map((d) => d.id).filter((id) => !fixos.has(id))].map((id, i) => [id, i + 1]));
}

/** As decisões que vão à resposta: as de nota ≥ 2, na ordem da seção, até MAX_RESPOSTA. As
 *  votadas ficam de fora: o voto não refaz a resposta. */
export function idsParaResposta(s: Secoes, avaliacoes: Map<string, Avaliacao>): string[] {
  return s.relacionadas
    .filter((d) => (avaliacoes.get(d.id)?.nota ?? 0) >= 2)
    .slice(0, MAX_RESPOSTA)
    .map((d) => d.id);
}
