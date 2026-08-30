import type { Outcome } from "@/lib/outcome";

export interface Decision {
  id: string;
  title: string;
  court: string;
  chamber: string;
  date: string;
  outcome: Outcome;
  relevance: number;
  rapporteur: string;
  processNumber: string;
  summary: string;
  tags: string[];
  matchedEntities: string[];
}

/** Resultados mockados (Figuras 4-5 da RFC), até a API de busca híbrida existir. Fonte única —
 *  compartilhada pela lista de resultados, o detalhe do acórdão e a lista de Salvos. */
export const mockResults: Decision[] = [
  {
    id: "1",
    title: "Adicional de insalubridade — exposição a agentes químicos cancerígenos",
    court: "TST",
    chamber: "3ª Turma",
    date: "2025-04-28",
    outcome: "favorable",
    relevance: 98,
    rapporteur: "Min. Alberto Bresciani",
    processNumber: "TST-RR-100-44.2021.5.01.0019",
    summary:
      "Mantida condenação ao pagamento de adicional de insalubridade em grau máximo ante a comprovação de exposição habitual e permanente a benzeno. Empresa tinha ciência do risco e não forneceu EPI eficaz. Laudo pericial confirmou a presença do agente nocivo acima dos limites de tolerância.",
    tags: ["NR-15", "CLT 192", "Benzeno", "Insalubridade grau máximo"],
    matchedEntities: ["Benzeno", "NR-15", "Ausência de EPI eficaz"],
  },
  {
    id: "2",
    title: "Responsabilidade patronal por exposição a agente insalubre sem monitoramento",
    court: "TRT-2",
    chamber: "14ª Turma",
    date: "2025-04-15",
    outcome: "favorable",
    relevance: 95,
    rapporteur: "Des. Carlos Roberto Barbosa",
    processNumber: "TRT2-ROT-1000523-31.2024.5.02.0066",
    summary:
      "Reconhecida a responsabilidade da empregadora pelo não fornecimento de proteção adequada e pela ausência de monitoramento de saúde ocupacional. Aplicação da Súmula 448 do TST. Trabalhador exposto a hidrocarbonetos aromáticos sem controle médico.",
    tags: ["Súmula 448 TST", "Monitoramento", "Hidrocarbonetos"],
    matchedEntities: ["Hidrocarbonetos aromáticos", "Exposição contínua sem monitoramento"],
  },
  {
    id: "3",
    title: "Uso de EPI como fator excludente do adicional de insalubridade",
    court: "TRT-15",
    chamber: "5ª Turma",
    date: "2025-03-22",
    outcome: "unfavorable",
    relevance: 82,
    rapporteur: "Des. Lorival Ferreira dos Santos",
    processNumber: "TRT15-ROT-0010234-19.2024.5.15.0089",
    summary:
      "Afastado o adicional de insalubridade ante a comprovação do fornecimento e uso efetivo de EPI adequado, capaz de neutralizar o agente nocivo. Perícia constatou o uso correto e a eficácia dos equipamentos fornecidos pela empresa.",
    tags: ["EPI", "Súmula 289 TST", "Neutralização"],
    matchedEntities: ["Ausência de EPI eficaz"],
  },
  {
    id: "4",
    title: "Insalubridade — necessidade de laudo técnico contemporâneo aos fatos",
    court: "TST",
    chamber: "8ª Turma",
    date: "2025-03-10",
    outcome: "neutral",
    relevance: 78,
    rapporteur: "Min. Dora Maria da Costa",
    processNumber: "TST-AIRR-20700-73.2023.5.04.0303",
    summary:
      "Indeferido pedido de adicional de insalubridade por ausência de prova técnica contemporânea aos fatos. Laudo pericial realizado após a rescisão contratual não se presta a demonstrar as condições de trabalho durante o período laborado.",
    tags: ["Laudo pericial", "Prova técnica", "CLT 195"],
    matchedEntities: ["NR-15"],
  },
  {
    id: "5",
    title: "Ciência patronal do risco e responsabilidade civil objetiva",
    court: "TRT-1",
    chamber: "7ª Turma",
    date: "2025-02-18",
    outcome: "favorable",
    relevance: 91,
    rapporteur: "Des. Ana Paula Tauceda Branco",
    processNumber: "TRT1-RO-0101234-56.2024.5.01.0048",
    summary:
      "Empresa tinha pleno conhecimento dos riscos à saúde do trabalhador, conforme documentação interna apresentada (PPP, PPRA, PCMSO). Caracterizada negligência no fornecimento de proteção adequada. Condenação em adicional de insalubridade e danos morais.",
    tags: ["Ciência patronal", "Dano moral", "Responsabilidade objetiva"],
    matchedEntities: ["Empresa ciente", "Falta de treinamento"],
  },
];

export function findDecision(id: string): Decision {
  return mockResults.find((d) => d.id === id) ?? mockResults[0];
}
