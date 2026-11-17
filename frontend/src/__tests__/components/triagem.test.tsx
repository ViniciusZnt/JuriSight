import { act, renderHook, waitFor } from "@testing-library/react";
import { useTriagem, TAMANHO_LOTE, EM_VOO } from "@/components/resultados/triagem";
import { ApiError, avaliarLote, emptyEstrutura, type Avaliacao, type ResultCard } from "@/lib/api";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), avaliarLote: jest.fn() }));

type Chamada = {
  ids: string[];
  apenasCache: boolean;
  signal?: AbortSignal;
  resolver: (r: Record<string, Avaliacao>, semEmenta?: string[]) => void;
  rejeitar: (e: unknown) => void;
};
let chamadas: Chamada[] = [];

beforeEach(() => {
  chamadas = [];
  (avaliarLote as jest.Mock).mockReset().mockImplementation(
    (_e: unknown, ids: string[], opcoes: { apenasCache?: boolean }, signal?: AbortSignal) =>
      new Promise((resolve, rejeitar) => {
        const resolver = (r: Record<string, Avaliacao>, semEmenta: string[] = []) => resolve({ avaliacoes: r, semEmenta });
        chamadas.push({ ids, apenasCache: !!opcoes.apenasCache, signal, resolver, rejeitar });
      }),
  );
});

// Cada teste usa ids próprios: o cache em memória do hook é por (ids + estrutura).
let serie = 0;
function cards(n: number): ResultCard[] {
  serie += 1;
  return Array.from({ length: n }, (_, i) => ({ id: `s${serie}-d${i}` }) as ResultCard);
}
const estrutura = { ...emptyEstrutura(), tese_central: "calor acima do limite" };
const av = (nota: 0 | 1 | 2 | 3): Avaliacao => ({ nota, posicao: "deferiu", motivo: "m" });
const notas = (ids: string[], nota: 0 | 1 | 2 | 3 = 3) => Object.fromEntries(ids.map((i) => [i, av(nota)]));

async function responder(c: Chamada, r: Record<string, Avaliacao> = notas(c.ids)) {
  await act(async () => c.resolver(r));
}
async function falhar(c: Chamada, e: unknown) {
  await act(async () => c.rejeitar(e));
}

test("constantes: lotes de 10, 2 em voo", () => {
  expect([TAMANHO_LOTE, EM_VOO]).toEqual([10, 2]);
});

test("dispara 2 lotes por vez e o 3º só quando um termina", async () => {
  const r = cards(30);
  renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  expect(chamadas.map((c) => c.ids)).toEqual([r.slice(0, 10).map((d) => d.id), r.slice(10, 20).map((d) => d.id)]);
  expect(chamadas.every((c) => !c.apenasCache)).toBe(true);
  await responder(chamadas[0], notas(chamadas[0].ids, 2));
  expect(chamadas).toHaveLength(3);
  expect(chamadas[2].ids).toEqual(r.slice(20).map((d) => d.id));
});

test("cada lote que chega entra em avaliacoes e avança avaliadas; termina em concluida", async () => {
  const r = cards(20);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  expect(result.current.status).toBe("avaliando");
  expect(result.current.total).toBe(20);
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[1], notas(chamadas[1].ids, 2));
  expect(result.current.avaliadas).toBe(10);
  expect(result.current.avaliacoes.get(r[10].id)?.nota).toBe(2);
  expect(result.current.status).toBe("avaliando");
  await responder(chamadas[0]);
  expect(result.current.avaliadas).toBe(20);
  expect(result.current.status).toBe("concluida");
});

test("parar descarta lote que chega depois", async () => {
  const r = cards(20);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  act(() => result.current.parar());
  expect(result.current.status).toBe("parada");
  expect(chamadas.every((c) => c.signal?.aborted)).toBe(true);
  await responder(chamadas[0]);
  expect(result.current.avaliadas).toBe(0);
  expect(result.current.status).toBe("parada");
});

test("continuar avalia só os que faltam", async () => {
  const r = cards(20);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0]);
  act(() => result.current.parar());
  act(() => result.current.continuar());
  expect(result.current.status).toBe("avaliando");
  await waitFor(() => expect(chamadas).toHaveLength(3));
  expect(chamadas[2].ids).toEqual(r.slice(10).map((d) => d.id));
  await responder(chamadas[2]);
  expect(result.current.status).toBe("concluida");
});

test("primeiro lote falha duas vezes → indisponivel e nenhum outro lote", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await falhar(chamadas[0], new ApiError("Avaliação por IA indisponível agora.", 503));
  expect(chamadas).toHaveLength(3); // nova tentativa do 1º lote
  expect(chamadas[2].ids).toEqual(chamadas[0].ids);
  await falhar(chamadas[2], new TypeError("Failed to fetch"));
  expect(result.current.status).toBe("indisponivel");
  expect(chamadas[1].signal?.aborted).toBe(true);
  expect(chamadas).toHaveLength(3);
});

test("lote do meio falha duas vezes → segue com os outros e os ids dele ficam sem avaliação", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0], notas(chamadas[0].ids, 2)); // dispara o 3º lote
  await falhar(chamadas[1], new ApiError("Erro 500.", 500));
  const nova = chamadas.find((c, i) => i > 1 && c.ids[0] === r[10].id)!;
  await falhar(nova, new ApiError("Erro 500.", 500));
  await responder(chamadas.find((c) => c.ids[0] === r[20].id)!);
  expect(result.current.avaliadas).toBe(20);
  expect(result.current.avaliacoes.has(r[10].id)).toBe(false);
  expect(result.current.status).toBe("parada"); // sobrou o que avaliar: o botão "Avaliar N restantes" aparece
});

test("429 para tudo e expõe a mensagem", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await falhar(chamadas[0], new ApiError("Você atingiu o limite de uso da IA de hoje.", 429));
  expect(result.current.status).toBe("parada");
  expect(result.current.erro).toBe("Você atingiu o limite de uso da IA de hoje.");
  expect(chamadas[1].signal?.aborted).toBe(true);
  expect(chamadas).toHaveLength(2);
});

test("reaberta (automatica false) usa só cache; faltando, fica ociosa", async () => {
  const r = cards(20);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: false }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  expect(chamadas.every((c) => c.apenasCache)).toBe(true);
  await responder(chamadas[0]);
  await responder(chamadas[1], {});
  expect(result.current.status).toBe("ociosa");
  expect(result.current.avaliadas).toBe(10);
});

test("reaberta com tudo em cache fica concluida", async () => {
  const r = cards(10);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: false }));
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await responder(chamadas[0]);
  expect(result.current.status).toBe("concluida");
});

test("sem resultados conclui sem chamar a API", () => {
  const { result } = renderHook(() => useTriagem(estrutura, [], { automatica: true }));
  expect(result.current.status).toBe("concluida");
  expect(avaliarLote).not.toHaveBeenCalled();
});

test("trocar a chave aborta os lotes da anterior", async () => {
  const a = cards(10);
  const b = cards(10);
  const { result, rerender } = renderHook(({ r }) => useTriagem(estrutura, r, { automatica: true }), {
    initialProps: { r: a },
  });
  await waitFor(() => expect(chamadas).toHaveLength(1));
  rerender({ r: b });
  expect(chamadas[0].signal?.aborted).toBe(true);
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0]); // a resposta da busca anterior não entra
  expect(result.current.avaliadas).toBe(0);
  await responder(chamadas[1]);
  expect(result.current.avaliadas).toBe(10);
});

test("voltar à tela não refaz a avaliação", async () => {
  const r = cards(10);
  const primeira = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await responder(chamadas[0]);
  primeira.unmount();
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  expect(result.current.status).toBe("concluida");
  expect(result.current.avaliadas).toBe(10);
  expect(chamadas).toHaveLength(1);
});

test("indisponivel não fica preso: ao reabrir, lê o cache de novo", async () => {
  const r = cards(10);
  const primeira = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await falhar(chamadas[0], new ApiError("fora", 503));
  await falhar(chamadas[1], new ApiError("fora", 503));
  expect(primeira.result.current.status).toBe("indisponivel");
  primeira.unmount();
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: false }));
  await waitFor(() => expect(chamadas).toHaveLength(3));
  expect(chamadas[2].apenasCache).toBe(true);
  await responder(chamadas[2]);
  expect(result.current.status).toBe("concluida");
});

test("leitura do cache interrompida é refeita ao voltar", async () => {
  const r = cards(20);
  const primeira = renderHook(() => useTriagem(estrutura, r, { automatica: false }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0]);
  primeira.unmount();
  renderHook(() => useTriagem(estrutura, r, { automatica: false }));
  await waitFor(() => expect(chamadas).toHaveLength(3));
  expect(chamadas[2].apenasCache).toBe(true);
  expect(chamadas[2].ids).toEqual(r.slice(10).map((d) => d.id));
});

test("indisponivel: continuar tenta de novo", async () => {
  const r = cards(10);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await falhar(chamadas[0], new ApiError("fora", 503));
  await falhar(chamadas[1], new ApiError("fora", 503));
  act(() => result.current.continuar());
  expect(result.current.status).toBe("avaliando");
  await waitFor(() => expect(chamadas).toHaveLength(3));
  expect(chamadas[2].apenasCache).toBe(false);
});

test("avaliouAqui: verdadeiro quando a IA avaliou nesta tela, falso na leitura só do cache", async () => {
  const r = cards(10);
  const nova = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  expect(nova.result.current.avaliouAqui).toBe(true);
  const r2 = cards(10);
  const reaberta = renderHook(() => useTriagem(estrutura, r2, { automatica: false }));
  expect(reaberta.result.current.avaliouAqui).toBe(false);
  await waitFor(() => expect(chamadas.some((ch) => ch.apenasCache)).toBe(true));
  act(() => reaberta.result.current.continuar());
  expect(reaberta.result.current.avaliouAqui).toBe(true);
});

test("sem ementa conta como processada: não fica faltando nem recebe nota", async () => {
  const r = cards(10);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(1));
  await act(async () => chamadas[0].resolver(notas(chamadas[0].ids.slice(2)), chamadas[0].ids.slice(0, 2)));
  expect(result.current.status).toBe("concluida");
  expect(result.current.avaliadas).toBe(10);
  expect([...result.current.semEmenta]).toEqual([r[0].id, r[1].id]);
  expect(result.current.avaliacoes.has(r[0].id)).toBe(false);
});

test("para sozinha ao achar 5 'Mesmo problema e fato': o lote em voo termina, os próximos não saem", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0], { ...notas(chamadas[0].ids.slice(0, 5), 3), ...notas(chamadas[0].ids.slice(5), 1) });
  expect(chamadas).toHaveLength(2);
  expect(result.current.status).toBe("avaliando");
  await responder(chamadas[1], notas(chamadas[1].ids, 0));
  expect(result.current.status).toBe("parada");
  expect(result.current.paradaAutomatica).toBe(true);
  expect(result.current.avaliadas).toBe(20);
  expect(chamadas).toHaveLength(2);
});

test("'Avaliar restantes' depois da parada automática não para sozinho", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0]);
  await responder(chamadas[1]);
  expect(result.current.paradaAutomatica).toBe(true);
  act(() => result.current.continuar());
  expect(result.current.paradaAutomatica).toBe(false);
  await waitFor(() => expect(chamadas).toHaveLength(3));
  await responder(chamadas[2]);
  expect(result.current.status).toBe("concluida");
});

test("com menos de 5 'Mesmo problema e fato' avalia tudo", async () => {
  const r = cards(30);
  const { result } = renderHook(() => useTriagem(estrutura, r, { automatica: true }));
  await waitFor(() => expect(chamadas).toHaveLength(2));
  await responder(chamadas[0], { ...notas(chamadas[0].ids.slice(0, 4), 3), ...notas(chamadas[0].ids.slice(4), 2) });
  expect(chamadas).toHaveLength(3);
  await responder(chamadas[1], notas(chamadas[1].ids, 2));
  await responder(chamadas[2], notas(chamadas[2].ids, 2));
  expect(result.current.status).toBe("concluida");
  expect(result.current.paradaAutomatica).toBe(false);
});
