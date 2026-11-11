import { render, screen, waitFor } from "@testing-library/react";
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

describe("faixas de resultado", () => {
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
    expect(await screen.findByText(/42 decisões citam CLT art\. 59 e contêm 'banco de horas'/)).toBeInTheDocument();
    expect(screen.queryByText(/Busca só semântica/)).not.toBeInTheDocument();
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

  it("faixa restrita vazia mostra o aviso com o acervo e não pede resposta", async () => {
    sessao.resultados = [];
    sessao.estrutura = restrita;
    render(<SearchResultsPage />);
    expect(await screen.findByText(/Nenhuma decisão do acervo \(≈70 mil acórdãos de 2025\) cita CLT art\. 59 e contém 'banco de horas'/)).toBeInTheDocument();
    expect(screen.getByText("Sem decisões no filtro restrito, a resposta não é gerada.")).toBeInTheDocument();
    expect(gerarResposta).not.toHaveBeenCalled();
  });
});
