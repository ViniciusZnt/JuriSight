import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchResultsPage } from "@/components/resultados/search-results-page";
import { contarFiltros, emptyEstrutura, gerarResposta, queryLivre, type ResultCard } from "@/lib/api";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }));
jest.mock("@/lib/conversations", () => ({ useConversations: () => ({ conversations: [], activeId: null }) }));
jest.mock("@/lib/saved", () => ({ useSaved: () => ({ isSaved: () => false, toggle: jest.fn() }) }));
jest.mock("@/components/provimento/provimento-panel", () => ({ ProvimentoPanel: () => null }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  contarFiltros: jest.fn(),
  queryLivre: jest.fn(),
  gerarResposta: jest.fn(),
  explicarBusca: jest.fn().mockResolvedValue({ semantica: "tese", termos: [] }),
}));
const sessao: { resultados: ResultCard[]; estrutura: ReturnType<typeof emptyEstrutura> } = { resultados: [], estrutura: emptyEstrutura() };
jest.mock("@/lib/search-session", () => ({
  useSearchSession: () => ({ ...sessao, versionNumero: 1, loadVersion: jest.fn() }),
}));

const card = (id: string, extra: Partial<ResultCard> = {}): ResultCard => ({
  id,
  tipo_documento: "acordao",
  hierarquia_categoria: 1,
  numero_processo: `000${id}`,
  tribunal: "TRT-2",
  turma: "1ª Turma",
  relator: "Fulano",
  data_julgamento: "2025-03-10",
  ementa: `Ementa da decisão ${id}`,
  provimento: "nao_classificado",
  link_original: null,
  score_rrf: 1,
  ...extra,
} as ResultCard);

const restrita = { ...emptyEstrutura(), dispositivos: ["CLT:59"], expressoes: ["banco de horas"] };

beforeEach(() => {
  (contarFiltros as jest.Mock).mockReset().mockResolvedValue({
    total: 42,
    dispositivos: [{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 100 }],
    expressoes: [{ texto: "banco de horas", total: 50 }],
  });
  (queryLivre as jest.Mock).mockReset().mockResolvedValue([]);
  (gerarResposta as jest.Mock).mockReset().mockResolvedValue({ frases: [], posicoes: [] });
});

describe("barra de filtros", () => {
  it("o segmento Neutras mostra só as decisões sem lado", async () => {
    sessao.resultados = [
      card("fav", { provimento: "NEGADO", ementa: "Ementa favorável" }),
      card("contra", { provimento: "APROVADO", ementa: "Ementa contrária" }),
      card("neutra", { provimento: "PARCIAL", ementa: "Ementa neutra" }),
    ];
    sessao.estrutura = emptyEstrutura();
    render(<SearchResultsPage />);

    await userEvent.click(screen.getByRole("button", { name: /Neutras\s*1/ }));

    expect(screen.getByText("Ementa neutra")).toBeInTheDocument();
    expect(screen.queryByText("Ementa favorável")).not.toBeInTheDocument();
    expect(screen.queryByText("Ementa contrária")).not.toBeInTheDocument();
  });
});

describe("faixas de resultado", () => {
  it("cada card diz por onde foi achado; card antigo, sem canais, não diz nada", () => {
    sessao.resultados = [card("a", { canais: ["semantica", "termos"] }), card("b", { canais: ["termos"] }), card("c")];
    sessao.estrutura = emptyEstrutura();
    render(<SearchResultsPage />);
    expect(screen.getByText("Achada pela semântica e pelos termos")).toBeInTheDocument();
    expect(screen.getByText("Achada pelos termos")).toBeInTheDocument();
    expect(screen.getAllByText(/^Achada pel/)).toHaveLength(2);
  });

  it("sem filtro mostra a lista sem faixas e a dica", () => {
    sessao.resultados = [card("a")];
    sessao.estrutura = emptyEstrutura();
    render(<SearchResultsPage />);
    expect(screen.getByText(/Busca só semântica\. Para restringir, informe dispositivos ou expressões na Revisão de Contexto\./)).toBeInTheDocument();
    expect(screen.queryByText("Busca livre (semântica)")).not.toBeInTheDocument();
    expect(contarFiltros).not.toHaveBeenCalled();
  });

  it("com filtro mostra a contagem no cabeçalho da faixa restrita", async () => {
    sessao.resultados = [card("a", { faixa: "restrita" })];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    const resumo = await screen.findByRole("region", { name: "Resumo das decisões" });
    expect(await within(resumo).findByText("42")).toBeInTheDocument();
    expect(within(resumo).getByText(/decisões do acervo/)).toBeInTheDocument();
    expect(within(resumo).getByText("CLT art. 59")).toBeInTheDocument();
    expect(within(resumo).getByText("banco de horas")).toBeInTheDocument();
    expect(within(resumo).getByText("Panorama da decisão mais relevante")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Filtro restrito" })).toBeInTheDocument();
    expect(screen.getByText(/Só entram decisões que citam todos os dispositivos/)).toBeInTheDocument();
    expect(screen.queryByText(/Busca só semântica/)).not.toBeInTheDocument();
  });

  it("sem contagem do acervo mostra o número de cards e o aviso, sem total antigo", async () => {
    (contarFiltros as jest.Mock).mockRejectedValue(new Error("503"));
    sessao.resultados = [card("a", { faixa: "restrita" }), card("b", { faixa: "restrita" })];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    expect(await screen.findByText("contagem do acervo indisponível")).toBeInTheDocument();
    expect(screen.getByText(/decisões cumprem o filtro/)).toBeInTheDocument();
    expect(screen.getByText("contagem do acervo indisponível")).toBeInTheDocument();
  });

  it("total maior que os cards mostra quantas aparecem", async () => {
    sessao.resultados = [card("a"), card("b"), card("c")];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    expect(await screen.findByText("Panorama das 3 mais relevantes")).toBeInTheDocument();
  });

  it("faixa livre começa fechada e só chama queryLivre ao abrir", async () => {
    sessao.resultados = [card("a", { faixa: "restrita" })];
    sessao.estrutura = restrita;
    (queryLivre as jest.Mock).mockResolvedValue([card("z", { faixa: "livre" })]);
    render(<SearchResultsPage />);
    expect(queryLivre).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Busca livre \(semântica\)/ }));
    expect(await screen.findByText("Ementa da decisão z")).toBeInTheDocument();
    expect(screen.getByText("Decisões parecidas, sem garantia de citar os dispositivos ou conter as expressões.")).toBeInTheDocument();
    expect(queryLivre).toHaveBeenCalledTimes(1);
    expect((queryLivre as jest.Mock).mock.calls[0][0].estrutura).toEqual(restrita);
  });

  it("faixa livre remove os ids que já estão na restrita", async () => {
    sessao.resultados = [card("a", { faixa: "restrita" })];
    sessao.estrutura = restrita;
    (queryLivre as jest.Mock).mockResolvedValue([card("a", { faixa: "livre" }), card("z", { faixa: "livre" })]);
    render(<SearchResultsPage />);
    await userEvent.click(screen.getByRole("button", { name: /Busca livre \(semântica\)/ }));
    await screen.findByText("Ementa da decisão z");
    expect(screen.getAllByText("Ementa da decisão a")).toHaveLength(1);
  });

  it("contagem em andamento aparece como contando, sem número do acervo", async () => {
    (contarFiltros as jest.Mock).mockReturnValue(new Promise(() => {}));
    sessao.resultados = [card("a", { faixa: "restrita" })];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    expect(await screen.findByText("contando no acervo…")).toBeInTheDocument();
    expect(screen.queryByText(/decisões do acervo/)).not.toBeInTheDocument();
  });

  it("chip da base citada não esconde a faixa livre", async () => {
    const cita = { ementa: "Aplica-se a Súmula 85 do TST ao caso." };
    sessao.resultados = [card("a", { faixa: "restrita", ...cita }), card("b", { faixa: "restrita", ...cita })];
    sessao.estrutura = restrita;
    (queryLivre as jest.Mock).mockResolvedValue([card("z", { faixa: "livre" })]);
    render(<SearchResultsPage />);
    await userEvent.click(screen.getByRole("button", { name: /Súmula 85 do TST/ }));
    await userEvent.click(screen.getByRole("button", { name: /Busca livre \(semântica\)/ }));
    expect(await screen.findByText("Ementa da decisão z")).toBeInTheDocument();
  });

  it("faixa restrita vazia mostra o aviso com o acervo e não pede resposta", async () => {
    sessao.resultados = [];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    expect(await screen.findByText(/decisões do acervo \(≈70 mil acórdãos de 2025\)/)).toBeInTheDocument();
    expect(screen.getByText("Abra a busca livre abaixo para ver decisões parecidas.")).toBeInTheDocument();
    expect(screen.getByText("Sem decisões no filtro restrito, a resposta não é gerada.")).toBeInTheDocument();
    expect(gerarResposta).not.toHaveBeenCalled();
  });
});
