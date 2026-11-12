import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { FiltroRestrito } from "@/components/revisao/filtro-restrito";
import { ApiError, contarFiltros, listarTribunais, sugerirDispositivos, type Fase } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  sugerirDispositivos: jest.fn(),
  contarFiltros: jest.fn(),
  listarTribunais: jest.fn(),
}));
const listar = listarTribunais as jest.Mock;
const sugerir = sugerirDispositivos as jest.Mock;
const contar = contarFiltros as jest.Mock;

function Harness({ ia = [] as string[], disp = [] as string[], exp = [] as string[], sugeridas = [] as { texto: string; total: number }[], dispSugeridos = [] as { codigo: string; rotulo: string; total: number }[], onBuscar = (() => {}) as (e: string[]) => void, onPatch = (() => {}) as (p: object) => void, normas = [] as string[] }) {
  const [d, setD] = useState(disp);
  const [e, setE] = useState(exp);
  const [n, setN] = useState(normas);
  const [t, setT] = useState<string[]>([]);
  const [f, setF] = useState<Fase | null>(null);
  return (
    <>
      <FiltroRestrito
        dispositivos={d}
        expressoes={e}
        normas={n}
        tribunais={t}
        fase={f}
        dispositivosIa={ia}
        expressoesSugeridas={sugeridas}
        dispositivosSugeridos={dispSugeridos}
        onChange={(p) => {
          if (p.dispositivos) setD(p.dispositivos);
          if (p.expressoes) setE(p.expressoes);
          if (p.normas) setN(p.normas);
          if (p.tribunais) setT(p.tribunais);
          if (p.fase !== undefined) setF(p.fase);
          onPatch(p);
        }}
      />
      <button onClick={() => onBuscar(e)}>Buscar jurisprudências</button>
    </>
  );
}

beforeEach(() => {
  sugerir.mockReset().mockResolvedValue([]);
  contar.mockReset().mockResolvedValue({ total: 0, dispositivos: [], expressoes: [] });
  listar.mockReset().mockResolvedValue([
    { tribunal: "TRT2", rotulo: "TRT-2", total: 10 },
    { tribunal: "TRT4", rotulo: "TRT-4", total: 20 },
  ]);
});

describe("FiltroRestrito", () => {
  it("sugere e adiciona o código escolhido, mostrando o rótulo", async () => {
    sugerir.mockResolvedValue([{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 120 }]);
    contar.mockResolvedValue({ total: 120, dispositivos: [{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 120 }], expressoes: [] });
    render(<Harness />);
    await userEvent.type(screen.getByPlaceholderText(/buscar dispositivo/i), "clt 59");
    await userEvent.click(await screen.findByText("CLT art. 59 · 120 decisões"));
    expect(await screen.findByText("CLT art. 59")).toBeInTheDocument();
    expect(sugerir).toHaveBeenCalledWith("clt 59");
  });

  it('Enter com texto livre vira chip "só busca livre" e entra em normas', async () => {
    const onPatch = jest.fn();
    render(<Harness onPatch={onPatch} />);
    await userEvent.type(screen.getByPlaceholderText(/buscar dispositivo/i), "NR 99{Enter}");
    expect(onPatch).toHaveBeenCalledWith({ normas: ["NR 99"] });
    expect(screen.getByText("NR 99")).toBeInTheDocument();
    expect(screen.getByText("só busca livre")).toBeInTheDocument();
    expect(screen.getByLabelText("Buscar dispositivo legal")).toHaveValue("");
  });

  it("Enter com texto que bate com um código continua só busca livre", async () => {
    sugerir.mockResolvedValue([{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 1 }]);
    const onPatch = jest.fn();
    render(<Harness onPatch={onPatch} />);
    await userEvent.type(screen.getByLabelText("Buscar dispositivo legal"), "CLT art. 59{Enter}");
    expect(onPatch).toHaveBeenCalledWith({ normas: ["CLT art. 59"] });
    expect(onPatch).not.toHaveBeenCalledWith(expect.objectContaining({ dispositivos: expect.anything() }));
  });

  it('remover chip "só busca livre" atualiza normas', async () => {
    const onPatch = jest.fn();
    render(<Harness normas={["NR 99", "NR 15"]} onPatch={onPatch} />);
    await userEvent.click(screen.getByRole("button", { name: "Remover NR 99" }));
    expect(onPatch).toHaveBeenCalledWith({ normas: ["NR 15"] });
  });

  it('lápis do chip "só busca livre" leva o texto à busca', async () => {
    render(<Harness normas={["NR 99"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Editar NR 99" }));
    expect(screen.getByLabelText("Buscar dispositivo legal")).toHaveValue("NR 99");
    expect(screen.queryByRole("button", { name: "Remover NR 99" })).not.toBeInTheDocument();
  });

  it("campo se chama Normas e dispositivos", () => {
    render(<Harness />);
    expect(screen.getByText("Normas e dispositivos")).toBeInTheDocument();
  });

  it('chip de dispositivo da IA mostra "sugestão da IA"', async () => {
    render(<Harness disp={["CLT:59"]} ia={["CLT:59"]} />);
    expect(await screen.findByText("sugestão da IA")).toBeInTheDocument();
  });

  it("expressão adicionada com Enter mostra a contagem", async () => {
    contar.mockResolvedValue({ total: 7, dispositivos: [], expressoes: [{ texto: "hora extra", total: 7 }] });
    render(<Harness />);
    await userEvent.type(screen.getByPlaceholderText(/expressão/i), "hora extra{Enter}");
    expect(await screen.findByText(/· 7 decisões/)).toBeInTheDocument();
    expect(await screen.findByText("Com todos os filtros: 7 decisões")).toBeInTheDocument();
  });

  it("mostra contando… enquanto a contagem nova não chega, sem o total anterior", async () => {
    contar.mockResolvedValueOnce({ total: 7, dispositivos: [], expressoes: [{ texto: "hora extra", total: 7 }] });
    let responder: (v: unknown) => void = () => {};
    contar.mockReturnValueOnce(new Promise((r) => (responder = r)));
    render(<Harness exp={["hora extra"]} />);
    expect(await screen.findByText("Com todos os filtros: 7 decisões")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText(/expressão/i), "banco de horas{Enter}");
    expect(await screen.findByText("Com todos os filtros: contando…")).toBeInTheDocument();
    expect(screen.queryByText("Com todos os filtros: 7 decisões")).not.toBeInTheDocument();
    responder({ total: 2, dispositivos: [], expressoes: [{ texto: "hora extra", total: 7 }, { texto: "banco de horas", total: 3 }] });
    expect(await screen.findByText("Com todos os filtros: 2 decisões")).toBeInTheDocument();
    expect(screen.queryByText(/contando…/)).not.toBeInTheDocument();
  });

  it("texto digitado sem Enter entra como chip ao clicar em Buscar", async () => {
    const onBuscar = jest.fn();
    render(<Harness onBuscar={onBuscar} />);
    await userEvent.type(screen.getByPlaceholderText(/expressão/i), "  dano moral coletivo ");
    await userEvent.click(screen.getByRole("button", { name: "Buscar jurisprudências" }));
    expect(onBuscar).toHaveBeenCalledWith(["dano moral coletivo"]);
    expect(screen.getByLabelText("Nova expressão obrigatória")).toHaveValue("");
  });

  it("campo de expressão aceita no máximo 200 caracteres", () => {
    render(<Harness />);
    expect(screen.getByLabelText("Nova expressão obrigatória")).toHaveAttribute("maxLength", "200");
  });

  it("contagem zero mostra o aviso de faixa vazia", async () => {
    render(<Harness exp={["xyz"]} />);
    expect(await screen.findByText(/Nenhuma decisão do acervo cumpre todos os filtros/)).toBeInTheDocument();
  });

  it("expressão sugerida pela IA só vira filtro depois do clique", async () => {
    render(<Harness sugeridas={[{ texto: "dano moral coletivo", total: 137 }]} />);
    expect(screen.queryByRole("button", { name: "Remover dano moral coletivo" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "+ dano moral coletivo · 137 decisões" }));

    expect(screen.getByRole("button", { name: "Remover dano moral coletivo" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ dano moral coletivo · 137 decisões" })).not.toBeInTheDocument();
  });

  it("dispositivo sugerido pela IA só vira filtro depois do clique, com o rótulo", async () => {
    contar.mockRejectedValue(new ApiError("x", 503)); // o rótulo vem da sugestão, não da contagem
    render(<Harness dispSugeridos={[{ codigo: "b_ii_art_10_adct", rotulo: "ADCT art. 10, II, b", total: 163 }]} />);
    expect(screen.queryByRole("button", { name: "Remover ADCT art. 10, II, b" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "+ ADCT art. 10, II, b · 163 decisões" }));

    expect(screen.getByRole("button", { name: "Remover ADCT art. 10, II, b" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ ADCT art. 10, II, b · 163 decisões" })).not.toBeInTheDocument();
  });

  it("erro nas sugestões avisa em vez de não abrir a lista", async () => {
    sugerir.mockRejectedValue(new ApiError("x", 503));
    render(<Harness />);
    await userEvent.type(screen.getByPlaceholderText(/buscar dispositivo/i), "clt 59");
    expect(await screen.findByText("Filtro restrito indisponível no momento")).toBeInTheDocument();
  });

  it("busca sem resultado avisa que o dispositivo não está no acervo", async () => {
    render(<Harness />);
    await userEvent.type(screen.getByPlaceholderText(/buscar dispositivo/i), "nr 15");
    expect(await screen.findByText(/Nenhum dispositivo do acervo para “nr 15”/)).toBeInTheDocument();
  });

  it("erro na contagem mostra indisponível sem quebrar", async () => {
    contar.mockRejectedValue(new ApiError("x", 503));
    render(<Harness exp={["xyz"]} />);
    await waitFor(() => expect(screen.getByText("Filtro restrito indisponível no momento")).toBeInTheDocument());
  });

  it("lápis da expressão devolve o texto ao campo e remove o chip", async () => {
    render(<Harness exp={["hora extra"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Editar hora extra" }));
    const input = screen.getByLabelText("Nova expressão obrigatória");
    expect(input).toHaveValue("hora extra");
    expect(input).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Editar hora extra" })).not.toBeInTheDocument();
  });

  it("lápis do dispositivo leva o rótulo à busca e remove o chip", async () => {
    sugerir.mockResolvedValue([{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 1 }]);
    render(<Harness />);
    await userEvent.type(screen.getByLabelText("Buscar dispositivo legal"), "clt");
    await userEvent.click(await screen.findByText("CLT art. 59 · 1 decisões"));
    await userEvent.click(screen.getByRole("button", { name: "Editar CLT art. 59" }));
    const busca = screen.getByLabelText("Buscar dispositivo legal");
    expect(busca).toHaveValue("CLT art. 59");
    expect(busca).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Remover CLT art. 59" })).not.toBeInTheDocument();
  });

  it("chip escolhido mostra o rótulo mesmo se a contagem falhar", async () => {
    sugerir.mockResolvedValue([{ codigo: "CLT:59", rotulo: "CLT art. 59", total: 1 }]);
    contar.mockRejectedValue(new ApiError("x", 503));
    render(<Harness />);
    await userEvent.type(screen.getByLabelText("Buscar dispositivo legal"), "clt");
    await userEvent.click(await screen.findByText("CLT art. 59 · 1 decisões"));
    expect(await screen.findByText("Filtro restrito indisponível no momento")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remover CLT art. 59" })).toBeInTheDocument();
    expect(screen.queryByText("CLT:59")).not.toBeInTheDocument();
  });

  it("escolhe tribunal na lista, vira chip e entra na contagem", async () => {
    const onPatch = jest.fn();
    render(<Harness onPatch={onPatch} />);
    await userEvent.click(screen.getByRole("button", { name: "Todos os tribunais" }));
    await userEvent.click(await screen.findByText("TRT-4 · 20 decisões"));
    expect(onPatch).toHaveBeenCalledWith({ tribunais: ["TRT4"] });
    expect(await screen.findByRole("button", { name: "Remover TRT-4" })).toBeInTheDocument();
    await waitFor(() => expect(contar).toHaveBeenLastCalledWith({ dispositivos: [], expressoes: [], tribunais: ["TRT4"], fase: null }));
    await userEvent.click(screen.getByRole("button", { name: "Remover TRT-4" }));
    expect(onPatch).toHaveBeenLastCalledWith({ tribunais: [] });
  });

  it("segmento de fase chama onChange e entra na contagem", async () => {
    const onPatch = jest.fn();
    render(<Harness onPatch={onPatch} />);
    await userEvent.click(screen.getByRole("button", { name: "Execução" }));
    expect(onPatch).toHaveBeenCalledWith({ fase: "execucao" });
    await waitFor(() => expect(contar).toHaveBeenLastCalledWith({ dispositivos: [], expressoes: [], tribunais: [], fase: "execucao" }));
  });

  it("falha na lista de tribunais mostra aviso e reabrir tenta de novo", async () => {
    listar.mockRejectedValueOnce(new Error("503"));
    render(<Harness />);
    const abrir = screen.getByRole("button", { name: "Todos os tribunais" });
    await userEvent.click(abrir);
    expect(await screen.findByText("Lista de tribunais indisponível")).toBeInTheDocument();
    await userEvent.click(abrir);
    await userEvent.click(abrir);
    expect(await screen.findByText("TRT-4 · 20 decisões")).toBeInTheDocument();
  });

  it("Esc e clique fora fecham o menu de tribunais", async () => {
    render(<Harness />);
    const abrir = screen.getByRole("button", { name: "Todos os tribunais" });
    await userEvent.click(abrir);
    expect(await screen.findByText("TRT-4 · 20 decisões")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByText("TRT-4 · 20 decisões")).not.toBeInTheDocument();
    await userEvent.click(abrir);
    expect(await screen.findByText("TRT-4 · 20 decisões")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Execução" }));
    expect(screen.queryByText("TRT-4 · 20 decisões")).not.toBeInTheDocument();
  });
});
