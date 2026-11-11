import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { FiltroRestrito } from "@/components/revisao/filtro-restrito";
import { ApiError, contarFiltros, sugerirDispositivos } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  sugerirDispositivos: jest.fn(),
  contarFiltros: jest.fn(),
}));
const sugerir = sugerirDispositivos as jest.Mock;
const contar = contarFiltros as jest.Mock;

function Harness({ ia = [] as string[], disp = [] as string[], exp = [] as string[] }) {
  const [d, setD] = useState(disp);
  const [e, setE] = useState(exp);
  return (
    <FiltroRestrito
      dispositivos={d}
      expressoes={e}
      dispositivosIa={ia}
      onChange={(p) => {
        if (p.dispositivos) setD(p.dispositivos);
        if (p.expressoes) setE(p.expressoes);
      }}
    />
  );
}

beforeEach(() => {
  sugerir.mockReset().mockResolvedValue([]);
  contar.mockReset().mockResolvedValue({ total: 0, dispositivos: [], expressoes: [] });
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

  it("texto sem escolher da lista não vira chip", async () => {
    const onChange = jest.fn();
    render(<FiltroRestrito dispositivos={[]} expressoes={[]} dispositivosIa={[]} onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText(/buscar dispositivo/i), "clt 59{Enter}");
    expect(onChange).not.toHaveBeenCalled();
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

  it("contagem zero mostra o aviso de faixa vazia", async () => {
    render(<Harness exp={["xyz"]} />);
    expect(await screen.findByText(/Nenhuma decisão do acervo cumpre todos os filtros/)).toBeInTheDocument();
  });

  it("erro na contagem mostra indisponível sem quebrar", async () => {
    contar.mockRejectedValue(new ApiError("x", 503));
    render(<Harness exp={["xyz"]} />);
    await waitFor(() => expect(screen.getByText("Filtro restrito indisponível no momento")).toBeInTheDocument());
  });
});
