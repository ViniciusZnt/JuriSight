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
}

/** Separa os resultados (na ordem do RRF) em três seções:
 *  - relacionadas: nota 3, depois 2 (empate na ordem do RRF), e por fim as que o advogado marcou
 *    "É relevante", na ordem do voto;
 *  - não avaliadas: na ordem do RRF;
 *  - pouco relacionadas: nota 1, depois 0. */
export function organizar(resultados: ResultCard[], avaliacoes: Map<string, Avaliacao>, relevantesUsuario: string[]): Secoes {
  const votadas = new Set(relevantesUsuario);
  const porNota = (a: ResultCard, b: ResultCard) => avaliacoes.get(b.id)!.nota - avaliacoes.get(a.id)!.nota;
  const avaliadas = resultados.filter((d) => avaliacoes.has(d.id) && !votadas.has(d.id));
  const porId = new Map(resultados.map((d) => [d.id, d]));
  return {
    relacionadas: [
      ...avaliadas.filter((d) => avaliacoes.get(d.id)!.nota >= 2).sort(porNota),
      ...relevantesUsuario.flatMap((id) => porId.get(id) ?? []),
    ],
    naoAvaliadas: resultados.filter((d) => !avaliacoes.has(d.id) && !votadas.has(d.id)),
    poucoRelacionadas: avaliadas.filter((d) => avaliacoes.get(d.id)!.nota < 2).sort(porNota),
  };
}

/** #1..#N na ordem relacionadas → não avaliadas → pouco relacionadas (a que a resposta cita). */
export function numeracao(s: Secoes): Map<string, number> {
  return new Map([...s.relacionadas, ...s.naoAvaliadas, ...s.poucoRelacionadas].map((d, i) => [d.id, i + 1]));
}

/** As decisões que vão à resposta: as de nota ≥ 2, na ordem da seção, até MAX_RESPOSTA. As
 *  votadas ficam de fora: o voto não refaz a resposta. */
export function idsParaResposta(s: Secoes, avaliacoes: Map<string, Avaliacao>): string[] {
  return s.relacionadas
    .filter((d) => (avaliacoes.get(d.id)?.nota ?? 0) >= 2)
    .slice(0, MAX_RESPOSTA)
    .map((d) => d.id);
}
