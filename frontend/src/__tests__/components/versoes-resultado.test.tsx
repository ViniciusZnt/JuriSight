import { render, screen } from "@testing-library/react";
import { SearchResultsPage } from "@/components/resultados/search-results-page";
import { emptyEstrutura, type ResultCard } from "@/lib/api";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }));
jest.mock("@/lib/conversations", () => ({ useConversations: () => ({ conversations: [], activeId: null }) }));
jest.mock("@/lib/saved", () => ({ useSaved: () => ({ isSaved: () => false, toggle: jest.fn() }) }));
jest.mock("@/components/provimento/provimento-panel", () => ({ ProvimentoPanel: () => null }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  contarFiltros: jest.fn().mockResolvedValue({ total: 5, dispositivos: [], expressoes: [] }),
  queryLivre: jest.fn().mockResolvedValue([]),
  gerarResposta: jest.fn().mockResolvedValue({ frases: [], posicoes: [] }),
  explicarBusca: jest.fn().mockResolvedValue({ semantica: "tese", termos: [] }),
}));
const sessao: { resultados: ResultCard[]; estrutura: ReturnType<typeof emptyEstrutura>; versionNumero: number } = { resultados: [], estrutura: emptyEstrutura(), versionNumero: 1 };
jest.mock("@/lib/search-session", () => ({ useSearchSession: () => ({ ...sessao, loadVersion: jest.fn() }) }));

it("trocar de versão não acumula o painel \"Como esta busca foi feita\" (keys únicas entre irmãos)", async () => {
  sessao.resultados = [];
  sessao.estrutura = { ...emptyEstrutura(), tese_central: "t", expressoes: ["horas extras"] };
  const { rerender } = render(<SearchResultsPage />);
  for (const [v, e] of [[2, ["motorista"]], [3, ["horas extras", "motorista"]]] as const) {
    sessao.versionNumero = v;
    sessao.estrutura = { ...emptyEstrutura(), tese_central: "t", expressoes: [...e] };
    rerender(<SearchResultsPage />);
  }
  expect(await screen.findAllByRole("region", { name: "Como esta busca foi feita" })).toHaveLength(1);
});
