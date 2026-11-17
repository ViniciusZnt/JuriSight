import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchResultsPage } from "@/components/resultados/search-results-page";
import { ApiError, avaliarLote, emptyEstrutura, gerarResposta, type Avaliacao, type ResultCard } from "@/lib/api";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }));
const setRelevantes = jest.fn();
const salvarRespostaIds = jest.fn();
jest.mock("@/lib/conversations", () => ({
  useConversations: () => ({ conversations: [], activeId: "c1", setRelevantes, setRespostaIds: salvarRespostaIds }),
}));
jest.mock("@/lib/saved", () => ({ useSaved: () => ({ isSaved: () => false, toggle: jest.fn() }) }));
jest.mock("@/components/provimento/provimento-panel", () => ({ ProvimentoPanel: () => null }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  avaliarLote: jest.fn(),
  gerarResposta: jest.fn(),
  explicarBusca: jest.fn().mockResolvedValue({ semantica: "tese", termos: [] }),
}));
const setRelevantesUsuario = jest.fn();
const setRespostaIds = jest.fn();
const sessao = {
  resultados: [] as ResultCard[],
  estrutura: { ...emptyEstrutura(), tese_central: "calor acima do limite" },
  versionNumero: 2,
  buscaNova: true,
  relevantesUsuario: [] as string[],
  respostaIds: [] as string[],
};
jest.mock("@/lib/search-session", () => ({
  useSearchSession: () => ({ ...sessao, loadVersion: jest.fn(), setRelevantesUsuario, setRespostaIds }),
}));

type Chamada = {
  ids: string[];
  apenasCache: boolean;
  resolver: (r: Record<string, Avaliacao>, semEmenta?: string[]) => void;
  rejeitar: (e: unknown) => void;
};
let chamadas: Chamada[] = [];
let serie = 0;

function cards(n: number): ResultCard[] {
  serie += 1;
  return Array.from({ length: n }, (_, i) => ({
    id: `p${serie}-d${i}`, tipo_documento: "acordao", hierarquia_categoria: 4, numero_processo: `000${i}`,
    tribunal: "TRT12", turma: "1ª Turma", relator: "Fulano", data_julgamento: "2025-03-10",
    ementa: `Ementa ${i}`, provimento: "nao_classificado", link_original: null, score_rrf: 100 - i,
  }) as unknown as ResultCard);
}
const av = (nota: 0 | 1 | 2 | 3): Avaliacao => ({ nota, posicao: "deferiu", motivo: `motivo ${nota}` });
const ordemNaTela = (c: HTMLElement) => [...c.querySelectorAll('[id^="decisao-"]')].map((e) => e.id.replace("decisao-", ""));

beforeEach(() => {
  chamadas = [];
  sessao.buscaNova = true;
  sessao.relevantesUsuario = [];
  sessao.respostaIds = [];
  setRelevantes.mockReset().mockResolvedValue(undefined);
  salvarRespostaIds.mockReset().mockResolvedValue(undefined);
  setRespostaIds.mockReset();
  setRelevantesUsuario.mockReset();
  (avaliarLote as jest.Mock).mockReset().mockImplementation(
    (_e: unknown, ids: string[], opcoes: { apenasCache?: boolean }) =>
      new Promise((resolve, rejeitar) =>
        chamadas.push({
          ids, apenasCache: !!opcoes.apenasCache, rejeitar,
          resolver: (r, semEmenta = []) => resolve({ avaliacoes: r, semEmenta }),
        }),
      ),
  );
  (gerarResposta as jest.Mock).mockReset().mockResolvedValue({ frases: [{ tipo: "resposta", texto: "Sim. Há adicional.", citacoes: [1] }] });
});

test("busca nova: mostra progresso e reordena quando o lote chega", async () => {
  const r = cards(3);
  sessao.resultados = r;
  const { container } = render(<SearchResultsPage />);
  expect(screen.getByText("Avaliando decisões com a IA… 0 de 3")).toBeInTheDocument();
  expect(screen.getByText("A resposta sai quando a avaliação terminar ou você parar.")).toBeInTheDocument();
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver({ [r[2].id]: av(3), [r[0].id]: av(2), [r[1].id]: av(0) }));
  expect(ordemNaTela(container)).toEqual([r[2].id, r[0].id]); // r[1] recolhida
  expect(screen.getByRole("button", { name: /Pouco relacionadas \(1\)/ })).toBeInTheDocument();
  expect(screen.getByText("Mesmo problema e fato")).toHaveAttribute("title", "motivo 3");
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledWith(sessao.estrutura, [r[2].id, r[0].id]));
  expect(await screen.findByText(/Há adicional/)).toBeInTheDocument();
});

test("parar e responder pede a resposta só com as relacionadas, na numeração congelada", async () => {
  const r = cards(15);
  sessao.resultados = r;
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(2));
  const lote0 = Object.fromEntries(r.slice(0, 10).map((d, i) => [d.id, av(i === 3 ? 3 : i === 0 ? 2 : 0)]));
  await act(async () => chamadas[0].resolver(lote0));
  await userEvent.click(screen.getByRole("button", { name: "Parar e responder" }));
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledWith(sessao.estrutura, [r[3].id, r[0].id]));
  await act(async () => chamadas[1].resolver(Object.fromEntries(r.slice(10).map((d) => [d.id, av(3)]))));
  expect(ordemNaTela(container).slice(0, 2)).toEqual([r[3].id, r[0].id]);
  expect(screen.getByRole("button", { name: "Avaliar 5 restantes" })).toBeInTheDocument();
  expect(gerarResposta).toHaveBeenCalledTimes(1);
});

test("pouco relacionadas ficam recolhidas; É relevante salva na versão", async () => {
  const r = cards(2);
  sessao.resultados = r;
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3), [r[1].id]: av(1) }));
  expect(ordemNaTela(container)).toEqual([r[0].id]);
  await userEvent.click(screen.getByRole("button", { name: /Pouco relacionadas \(1\)/ }));
  expect(ordemNaTela(container)).toEqual([r[0].id, r[1].id]);
  await userEvent.click(screen.getByRole("button", { name: "É relevante" }));
  expect(setRelevantesUsuario).toHaveBeenCalledWith([r[1].id]);
  expect(setRelevantes).toHaveBeenCalledWith("c1", 2, [r[1].id]);
});

test("decisão votada aparece nas relacionadas com 'Marcada por você' e pode desfazer", async () => {
  const r = cards(2);
  sessao.resultados = r;
  sessao.relevantesUsuario = [r[1].id];
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3), [r[1].id]: av(0) }));
  expect(ordemNaTela(container)).toEqual([r[0].id, r[1].id]);
  expect(screen.getByText("Marcada por você")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
  expect(setRelevantes).toHaveBeenCalledWith("c1", 2, []);
});

test("OpenAI fora: aviso, lista na ordem da busca e sem bloco de resposta", async () => {
  const r = cards(3);
  sessao.resultados = r;
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].rejeitar(new ApiError("Avaliação por IA indisponível agora.", 503)));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await act(async () => chamadas[1].rejeitar(new ApiError("Avaliação por IA indisponível agora.", 503)));
  expect(screen.getByText("Avaliação por IA indisponível agora; a lista está na ordem da busca.")).toBeInTheDocument();
  expect(ordemNaTela(container)).toEqual(r.map((d) => d.id));
  expect(screen.queryByText(/A resposta sai quando/)).not.toBeInTheDocument();
  expect(gerarResposta).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  await waitFor(() => expect(chamadas).toHaveLength(3));
  expect(chamadas[2].apenasCache).toBe(false);
});

test("versão reaberta com tudo em cache não chama a IA e mostra a resposta", async () => {
  const r = cards(2);
  sessao.resultados = r;
  sessao.buscaNova = false;
  render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  expect(chamadas[0].apenasCache).toBe(true);
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3), [r[1].id]: av(2) }));
  expect(await screen.findByText(/Há adicional/)).toBeInTheDocument();
  expect(chamadas.every((c) => c.apenasCache)).toBe(true);
});

test("continuar depois de parar descarta a resposta e pede de novo ao concluir", async () => {
  const r = cards(15);
  sessao.resultados = r;
  render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await act(async () => chamadas[0].resolver(Object.fromEntries(r.slice(0, 10).map((d) => [d.id, av(2)]))));
  await userEvent.click(screen.getByRole("button", { name: "Parar e responder" }));
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledTimes(1));
  await userEvent.click(screen.getByRole("button", { name: "Avaliar 5 restantes" }));
  expect(screen.getByText("A resposta sai quando a avaliação terminar ou você parar.")).toBeInTheDocument();
  await waitFor(() => expect(chamadas).toHaveLength(3));
  await act(async () => chamadas[2].resolver(Object.fromEntries(r.slice(10).map((d) => [d.id, av(3)]))));
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledTimes(2));
  expect((gerarResposta as jest.Mock).mock.calls[1][1].slice(0, 5)).toEqual(r.slice(10).map((d) => d.id));
});

test("resposta gerada nesta tela é salva na versão (ids na ordem #1..#k)", async () => {
  const r = cards(2);
  sessao.resultados = r;
  render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver({ [r[1].id]: av(3), [r[0].id]: av(2) }));
  await waitFor(() => expect(salvarRespostaIds).toHaveBeenCalledWith("c1", 2, [r[1].id, r[0].id]));
  expect(setRespostaIds).toHaveBeenCalledWith([r[1].id, r[0].id]);
});

test("reaberta com resposta salva: mesmas decisões e numeração, mesmo se o cache tem mais avaliações", async () => {
  const r = cards(3);
  sessao.resultados = r;
  sessao.buscaNova = false;
  sessao.respostaIds = [r[2].id];
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  // o servidor terminou lotes depois do "Parar": agora r0 e r1 também têm nota alta
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3), [r[1].id]: av(3), [r[2].id]: av(2) }));
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledWith(sessao.estrutura, [r[2].id]));
  expect(gerarResposta).toHaveBeenCalledTimes(1);
  expect(ordemNaTela(container)[0]).toBe(r[2].id);
  expect(container.querySelector(`#decisao-${r[2].id}`)).toHaveTextContent("#1");
  expect(salvarRespostaIds).not.toHaveBeenCalled();
});

test("reaberta com decisões sem avaliação ainda mostra a resposta salva", async () => {
  const r = cards(12);
  sessao.resultados = r;
  sessao.buscaNova = false;
  sessao.respostaIds = [r[0].id];
  render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3) }));
  await act(async () => chamadas[1].resolver({}));
  expect(screen.getByRole("button", { name: "Avaliar 11 restantes" })).toBeInTheDocument();
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledWith(sessao.estrutura, [r[0].id]));
});

test("decisão sem ementa vai para 'Sem ementa (1)', sem selo de nota e fora da resposta", async () => {
  const r = cards(3);
  sessao.resultados = r;
  const { container } = render(<SearchResultsPage />);
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver({ [r[0].id]: av(3), [r[2].id]: av(2) }, [r[1].id]));
  expect(ordemNaTela(container)).toEqual([r[0].id, r[2].id]);
  await userEvent.click(screen.getByRole("button", { name: /Sem ementa \(1\)/ }));
  expect(ordemNaTela(container)).toEqual([r[0].id, r[2].id, r[1].id]);
  expect(container.querySelector(`#decisao-${r[1].id} [data-nota]`)).toBeNull();
  await waitFor(() => expect(gerarResposta).toHaveBeenCalledWith(sessao.estrutura, [r[0].id, r[2].id]));
});
