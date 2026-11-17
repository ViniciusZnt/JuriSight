import { act, render, screen } from "@testing-library/react";
import { PreviaBusca } from "@/components/revisao/previa-busca";
import { ApiError, emptyEstrutura, explicarBusca, rotuloTribunal, type EstruturaArgumentativa } from "@/lib/api";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), explicarBusca: jest.fn() }));

const base = { ...emptyEstrutura(), tese_central: "Tese X" };
const resposta = { semantica: "Tese X", termos: ["calor", "NR-15"], dispositivos: [] as string[] };

beforeEach(() => {
  jest.useFakeTimers();
  (explicarBusca as jest.Mock).mockReset().mockResolvedValue(resposta);
});
afterEach(() => jest.useRealTimers());

async function esperar(ms = 400) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

test("mostra termos, sentido e o que é exigido", async () => {
  (explicarBusca as jest.Mock).mockResolvedValue({ ...resposta, dispositivos: ["CLT art. 192"] });
  const estrutura: EstruturaArgumentativa = { ...base, expressoes: ["calor intenso"], tribunais: ["TRT12"], fase: "conhecimento" };
  render(<PreviaBusca estrutura={estrutura} />);
  await esperar();
  expect(screen.getByText("O que esta busca vai usar")).toBeInTheDocument();
  const termos = screen.getByText("Pelos termos").closest("div")!;
  expect(termos).toHaveTextContent("calor");
  expect(termos).toHaveTextContent("NR-15");
  expect(screen.getByText("Pelo sentido").closest("div")).toHaveTextContent("Tese X");
  const exige = screen.getByText("Exige").closest("div")!;
  expect(exige).toHaveTextContent("CLT art. 192");
  expect(exige).toHaveTextContent("“calor intenso”");
  expect(exige).toHaveTextContent(rotuloTribunal("TRT12"));
  expect(exige).toHaveTextContent("Conhecimento");
});

test("sem filtro diz que nada é exigido", async () => {
  render(<PreviaBusca estrutura={base} />);
  await esperar();
  expect(screen.getByText("Nada é exigido: todo o acervo entra")).toBeInTheDocument();
});

test("espera 400 ms depois da edição para chamar", async () => {
  const { rerender } = render(<PreviaBusca estrutura={base} />);
  await esperar(200);
  rerender(<PreviaBusca estrutura={{ ...base, tese_central: "Tese Y" }} />);
  await esperar(200);
  expect(explicarBusca).not.toHaveBeenCalled();
  await esperar(200);
  expect(explicarBusca).toHaveBeenCalledTimes(1);
  expect((explicarBusca as jest.Mock).mock.calls[0][0].tese_central).toBe("Tese Y");
});

test("resposta atrasada de edição anterior é ignorada", async () => {
  let resolverAntiga: (v: unknown) => void = () => {};
  (explicarBusca as jest.Mock)
    .mockImplementationOnce(() => new Promise((r) => (resolverAntiga = r)))
    .mockResolvedValueOnce({ ...resposta, semantica: "Nova" });
  const { rerender } = render(<PreviaBusca estrutura={base} />);
  await esperar();
  rerender(<PreviaBusca estrutura={{ ...base, tese_central: "Nova" }} />);
  await esperar();
  await act(async () => resolverAntiga({ ...resposta, semantica: "Antiga" }));
  expect(screen.getByText("Pelo sentido").closest("div")).toHaveTextContent("Nova");
  expect(screen.queryByText(/Antiga/)).not.toBeInTheDocument();
});

test("sem tese nem pedido mostra o aviso", async () => {
  (explicarBusca as jest.Mock).mockRejectedValue(new ApiError("vazia", 422));
  render(<PreviaBusca estrutura={emptyEstrutura()} />);
  await esperar();
  expect(screen.getByText("Preencha a tese central ou o pedido principal para buscar")).toBeInTheDocument();
});

test("erro esconde o quadro", async () => {
  (explicarBusca as jest.Mock).mockRejectedValue(new ApiError("fora", 500));
  render(<PreviaBusca estrutura={base} />);
  await esperar();
  expect(screen.queryByText("O que esta busca vai usar")).not.toBeInTheDocument();
});
