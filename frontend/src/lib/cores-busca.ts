/** Cores e nomes dos três jeitos de buscar (paleta A do guia de uso), num lugar só: o guia,
 *  o painel "Como esta busca foi feita", as marquinhas dos cartões e a Revisão usam estes
 *  valores, para que a mesma cor queira dizer a mesma coisa em todo o app.
 *  As classes Tailwind ficam escritas por extenso porque o Tailwind só gera o que aparece literal. */

export type Busca = "filtro" | "semantica" | "termos";

export interface EstiloBusca {
  nome: string;
  /** Cor da busca sobre fundo claro. */
  cor: string;
  /** Tom claro para usar sobre o marinho do painel dos resultados. */
  corSobreMarinho: string;
  /** Ponto/quadradinho sólido sobre fundo claro (com par escuro). */
  ponto: string;
  /** Ponto sobre o marinho do painel. */
  pontoSobreMarinho: string;
  /** Chip de exemplo/valor (fundo, borda e texto, claro e escuro). */
  chip: string;
  /** Etiqueta pequena ao lado do rótulo de um campo. */
  etiqueta: string;
}

/** Total de acórdãos do acervo, para "1.104 de 69.349 decisões" e para o guia. */
export const TOTAL_ACERVO = 69349;

export const BUSCA: Record<Busca, EstiloBusca> = {
  filtro: {
    nome: "Filtro restrito",
    cor: "#1A3A5C",
    corSobreMarinho: "#FFFFFF",
    ponto: "bg-[#1A3A5C] dark:bg-[#8AB0DC]",
    pontoSobreMarinho: "bg-white",
    chip: "bg-[#1A3A5C] border-[#1A3A5C] text-white dark:bg-[#8AB0DC] dark:border-[#8AB0DC] dark:text-[#0E0E11]",
    etiqueta: "bg-[#E9EEF5] text-[#1A3A5C] dark:bg-[#1A2A3C] dark:text-[#8AB0DC]",
  },
  semantica: {
    nome: "Busca semântica",
    cor: "#6D4FC2",
    corSobreMarinho: "#B6A5F0",
    ponto: "bg-[#6D4FC2] dark:bg-[#9A84E6]",
    pontoSobreMarinho: "bg-[#B6A5F0]",
    chip: "bg-[#F1EDFC] border-[#D5CAF3] text-[#46308C] dark:bg-[#211A38] dark:border-[#3E3270] dark:text-[#C9BCF5]",
    etiqueta: "bg-[#F1EDFC] text-[#5A3DAE] dark:bg-[#211A38] dark:text-[#C9BCF5]",
  },
  termos: {
    nome: "Busca por termos",
    cor: "#0E8A80",
    corSobreMarinho: "#5FCFC4",
    ponto: "bg-[#0E8A80] dark:bg-[#3FB8AD]",
    pontoSobreMarinho: "bg-[#5FCFC4]",
    chip: "bg-[#E6F5F3] border-[#BFE3DE] text-[#0B5F58] dark:bg-[#0F2826] dark:border-[#1E4A46] dark:text-[#7FD8CE]",
    etiqueta: "bg-[#E6F5F3] text-[#0B6F67] dark:bg-[#0F2826] dark:text-[#7FD8CE]",
  },
};
