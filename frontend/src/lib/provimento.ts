import type { ClassificacaoProvimento, Favorece, Provimento, Recorrente, ResultadoRecurso } from "@/lib/api";
import { provimentoToOutcome, type Outcome } from "@/lib/outcome";

export const RESULTADO_LABEL: Record<ResultadoRecurso, string> = {
  provido: "Provido",
  parcialmente_provido: "Provido em parte",
  nao_provido: "Não provido",
  nao_conhecido: "Não conhecido",
  sem_recurso: "Sem recurso",
};

export const RECORRENTE_LABEL: Record<Recorrente, string> = {
  reclamante: "Reclamante (trabalhador)",
  reclamada: "Reclamada (empresa)",
  ambos: "Ambas as partes",
  outro: "Outra parte",
  indefinido: "Não identificado",
};

export const FAVORECE_LABEL: Record<Favorece, string> = {
  reclamante: "Trabalhador",
  reclamada: "Empresa",
  ambos_em_parte: "Ambos em parte",
  indefinido: "Não identificado",
};

export const PROVIMENTO_LABEL: Record<Provimento, string> = {
  APROVADO: "Provido",
  PARCIAL: "Provido em parte",
  NEGADO: "Negado",
  NAO_APLICAVEL: "Não se aplica",
};

export type Pergunta = "resultado" | "recorrente" | "favorece";

export const PERGUNTAS: { chave: Pergunta; titulo: string; labels: Record<string, string> }[] = [
  { chave: "resultado", titulo: "Resultado do recurso", labels: RESULTADO_LABEL },
  { chave: "recorrente", titulo: "Quem recorreu", labels: RECORRENTE_LABEL },
  { chave: "favorece", titulo: "A quem favorece", labels: FAVORECE_LABEL },
];

export type NivelConfianca = "alta" | "media" | "baixa";

export function nivelConfianca(c: number | null | undefined): NivelConfianca {
  if (c == null) return "baixa";
  if (c >= 0.8) return "alta";
  if (c >= 0.5) return "media";
  return "baixa";
}

export function probabilidadesOrdenadas(p: Record<string, number> | undefined): { valor: string; prob: number }[] {
  return Object.entries(p ?? {})
    .map(([valor, prob]) => ({ valor, prob }))
    .sort((a, b) => b.prob - a.prob);
}

/** Selo Favorável/Desfavorável. Com classificação do Jev, vem de "a quem favorece" (o app parte
 *  do lado do trabalhador); sem ela, fica a heurística antiga sobre o provimento de 4 classes. */
export function outcomeDe(d: { provimento: Provimento; classificacao_provimento?: ClassificacaoProvimento | null }): Outcome {
  const c = d.classificacao_provimento;
  if (!c) return provimentoToOutcome(d.provimento);
  if ((c.confianca_favorece ?? 0) < 0.5) return "neutral";
  if (c.favorece === "reclamante") return "favorable";
  if (c.favorece === "reclamada") return "unfavorable";
  return "neutral";
}

/** Quantos resultados caem em cada selo — os três somam o total, para o resumo fechar a conta. */
export function contarDesfechos(ds: Parameters<typeof outcomeDe>[0][]): Record<Outcome, number> {
  const n: Record<Outcome, number> = { favorable: 0, unfavorable: 0, neutral: 0 };
  for (const d of ds) n[outcomeDe(d)]++;
  return n;
}

const RECURSO_DE: Record<Recorrente, string> = {
  reclamante: "Recurso do reclamante (trabalhador)",
  reclamada: "Recurso da reclamada (empresa)",
  ambos: "Recurso de ambas as partes",
  outro: "Recurso de outra parte",
  indefinido: "Recorrente não identificado",
};

export function resumoProvimento(c: ClassificacaoProvimento): string {
  return `${RECURSO_DE[c.recorrente]} · ${RESULTADO_LABEL[c.resultado]} · Favorece: ${FAVORECE_LABEL[c.favorece]}`;
}
