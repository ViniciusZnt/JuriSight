import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useTriagem } from "@/components/resultados/triagem";
import userEvent from "@testing-library/user-event";
import { UsoDiarioMenu } from "@/components/uso-diario";
import { PageTopbar } from "@/components/ui/page-topbar";
import { UsoDiarioProvider, useUsoDiario } from "@/lib/uso-diario";
import { avaliarLote, emptyEstrutura, getUso, type ResultCard } from "@/lib/api";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), getUso: jest.fn(), avaliarLote: jest.fn() }));

const uso = (query: number, triagem: number, limiteTriagem = 150) => ({
  acoes: [
    { acao: "enrich", usado: 0, limite: 30 },
    { acao: "query", usado: query, limite: 30 },
    { acao: "triagem", usado: triagem, limite: limiteTriagem },
    { acao: "resposta", usado: 0, limite: 30 },
  ],
});

function Gatilho() {
  const { atualizar } = useUsoDiario();
  return <button onClick={atualizar}>atualizar</button>;
}
const montar = () =>
  render(
    <UsoDiarioProvider>
      <Gatilho />
      <UsoDiarioMenu />
    </UsoDiarioProvider>,
  );

beforeEach(() => (getUso as jest.Mock).mockReset());

async function abrir() {
  await userEvent.click(await screen.findByRole("button", { name: /Uso de hoje/ }));
}

test("o topo mostra só o botão; clicar abre o detalhe por ação", async () => {
  (getUso as jest.Mock).mockResolvedValue(uso(3, 12));
  montar();
  await screen.findByRole("button", { name: /Uso de hoje/ });
  expect(screen.queryByText("Leitura do caso")).not.toBeInTheDocument();
  await abrir();
  expect(screen.getByText("Leitura do caso")).toBeInTheDocument();
  expect(screen.getByText("Buscas").closest("li")).toHaveTextContent("3 / 30");
  expect(screen.getByText("Avaliações da IA")).toHaveAttribute("title", "Cada lote de até 10 decisões conta 1");
  expect(screen.getByText("Avaliações da IA").closest("li")).toHaveTextContent("12 / 150");
  expect(screen.getByText("Respostas da IA")).toBeInTheDocument();
});

test("barra âmbar a partir de 80% e vermelha em 100%; o botão mostra a ação mais gasta", async () => {
  (getUso as jest.Mock).mockResolvedValue(uso(24, 150));
  montar();
  expect(await screen.findByRole("button", { name: /Uso de hoje/ })).toHaveAttribute("data-nivel", "esgotado");
  await abrir();
  expect(screen.getByText("Buscas").closest("li")).toHaveAttribute("data-nivel", "alerta");
  expect(screen.getByText("Avaliações da IA").closest("li")).toHaveAttribute("data-nivel", "esgotado");
  expect(screen.getByText("Leitura do caso").closest("li")).toHaveAttribute("data-nivel", "normal");
});

test("falha do /uso esconde o botão", async () => {
  (getUso as jest.Mock).mockRejectedValue(new Error("503"));
  montar();
  await waitFor(() => expect(getUso).toHaveBeenCalled());
  expect(screen.queryByRole("button", { name: /Uso de hoje/ })).not.toBeInTheDocument();
});

test("atualizar() busca de novo e re-renderiza", async () => {
  (getUso as jest.Mock).mockResolvedValueOnce(uso(3, 0)).mockResolvedValueOnce(uso(4, 5));
  montar();
  await abrir();
  await act(async () => screen.getByRole("button", { name: "atualizar" }).click());
  await waitFor(() => expect(screen.getByText("Buscas").closest("li")).toHaveTextContent("4 / 30"));
});

test("fora do provider, useUsoDiario não quebra", () => {
  function Solto() {
    const { acoes, atualizar: a } = useUsoDiario();
    a();
    return <span>{acoes === null ? "sem" : "com"}</span>;
  }
  render(<Solto />);
  expect(screen.getByText("sem")).toBeInTheDocument();
});

test("cada lote da triagem que termina atualiza o uso; a leitura só do cache não", async () => {
  (getUso as jest.Mock).mockResolvedValue(uso(0, 0));
  (avaliarLote as jest.Mock).mockReset().mockResolvedValue({ avaliacoes: {}, semEmenta: [] });
  const r = Array.from({ length: 15 }, (_, i) => ({ id: `uso-d${i}` }) as ResultCard);
  const est = { ...emptyEstrutura(), tese_central: "t" };
  const wrapper = ({ children }: { children: React.ReactNode }) => <UsoDiarioProvider>{children}</UsoDiarioProvider>;
  const { result } = renderHook(() => useTriagem(est, r, { automatica: true }), { wrapper });
  await waitFor(() => expect(result.current.status).not.toBe("avaliando"));
  await waitFor(() => expect(getUso).toHaveBeenCalledTimes(3)); // montagem + 2 lotes
  (getUso as jest.Mock).mockClear();
  renderHook(() => useTriagem(est, r.slice(0, 5).map((d) => ({ id: `${d.id}-c` }) as ResultCard), { automatica: false }), { wrapper });
  await waitFor(() => expect(avaliarLote).toHaveBeenLastCalledWith(est, expect.any(Array), { apenasCache: true }, expect.anything()));
  await waitFor(() => expect(getUso).toHaveBeenCalledTimes(1)); // só a montagem do provider
});

test("Esc fecha o detalhe", async () => {
  (getUso as jest.Mock).mockResolvedValue(uso(3, 12));
  montar();
  await abrir();
  expect(screen.getByText("Buscas")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByText("Buscas")).not.toBeInTheDocument();
});

test("o cabeçalho das telas traz o uso de hoje", async () => {
  (getUso as jest.Mock).mockResolvedValue(uso(1, 1));
  render(
    <UsoDiarioProvider>
      <PageTopbar crumbs={[{ label: "Início" }]} />
    </UsoDiarioProvider>,
  );
  expect(await screen.findByRole("button", { name: /Uso de hoje/ })).toBeInTheDocument();
});
