import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EntityReviewPage } from "@/components/revisao/entity-review-page";
import { FaixaLivre } from "@/components/resultados/faixa-livre";
import { emptyEstrutura, queryJurisprudencia, queryLivre } from "@/lib/api";

const push = jest.fn();
const loadVersion = jest.fn();
const addVersion = jest.fn();
let mockActiveId: string | null = null;
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }), useSearchParams: () => new URLSearchParams("modo=manual") }));
jest.mock("@/lib/conversations", () => ({ useConversations: () => ({ activeId: mockActiveId, addVersion }) }));
jest.mock("@/lib/search-session", () => ({
  useSearchSession: () => ({
    estrutura: null, hasFile: false, fileName: null, pdfExtraido: null, aviso: null,
    dispositivosIa: [], expressoesSugeridas: [], dispositivosSugeridos: [], setEstrutura: jest.fn(), loadVersion,
  }),
}));
jest.mock("@/components/revisao/filtro-restrito", () => ({ FiltroRestrito: () => null }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  queryJurisprudencia: jest.fn(),
  queryLivre: jest.fn(),
}));

// Uma busca que só termina quando o teste manda; rejeita como o fetch quando o sinal aborta.
function pendente(mock: jest.Mock) {
  let resolver: (v: unknown[]) => void = () => {};
  mock.mockImplementation(
    (_corpo: unknown, signal?: AbortSignal) =>
      new Promise((res, rej) => {
        resolver = res;
        signal?.addEventListener("abort", () => rej(new Error("abortada")));
      }),
  );
  return (v: unknown[]) => resolver(v);
}

beforeEach(() => {
  jest.clearAllMocks();
  mockActiveId = null;
});

test("Revisão: resposta que chega depois de sair da tela não cria versão nem navega", async () => {
  const responder = pendente(queryJurisprudencia as jest.Mock);
  const { unmount } = render(<EntityReviewPage />);
  await userEvent.click(screen.getByRole("button", { name: /Buscar jurisprudências/ }));
  expect(queryJurisprudencia).toHaveBeenCalledTimes(1);

  unmount();
  responder([]);
  await new Promise((r) => setTimeout(r, 0));

  expect((queryJurisprudencia as jest.Mock).mock.calls[0][1].aborted).toBe(true);
  expect(loadVersion).not.toHaveBeenCalled();
  expect(push).not.toHaveBeenCalled();
});

test("Revisão: sair da tela durante o salvamento da versão não navega", async () => {
  mockActiveId = "conversa-1";
  (queryJurisprudencia as jest.Mock).mockResolvedValue([]);
  let terminarSalvamento: (v: unknown) => void = () => {};
  addVersion.mockReturnValue(new Promise((res) => (terminarSalvamento = res)));
  const { unmount } = render(<EntityReviewPage />);
  await userEvent.click(screen.getByRole("button", { name: /Buscar jurisprudências/ }));
  await waitFor(() => expect(addVersion).toHaveBeenCalledTimes(1));

  unmount();
  terminarSalvamento({ numero: 1 });
  await new Promise((r) => setTimeout(r, 0));

  expect(loadVersion).not.toHaveBeenCalled();
  expect(push).not.toHaveBeenCalled();
});

test("Revisão: sem sair da tela a busca segue normalmente", async () => {
  (queryJurisprudencia as jest.Mock).mockResolvedValue([]);
  render(<EntityReviewPage />);
  await userEvent.click(screen.getByRole("button", { name: /Buscar jurisprudências/ }));
  await waitFor(() => expect(push).toHaveBeenCalledWith("/resultados"));
});

test("Faixa livre: a busca em andamento é cancelada ao desmontar", async () => {
  pendente(queryLivre as jest.Mock);
  const { unmount } = render(<FaixaLivre estrutura={emptyEstrutura()} excluir={new Set()} passa={() => true} />);
  await userEvent.click(screen.getByRole("button", { name: /Busca livre/ }));
  unmount();
  expect((queryLivre as jest.Mock).mock.calls[0][1].aborted).toBe(true);
});
