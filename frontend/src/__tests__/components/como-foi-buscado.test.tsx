import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ComoFoiBuscado } from "@/components/resultados/como-foi-buscado";
import { emptyEstrutura, explicarBusca } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  explicarBusca: jest.fn(),
}));
const explicar = explicarBusca as jest.Mock;

const estrutura = { ...emptyEstrutura(), tese_central: "A empresa violou o segredo industrial." };

beforeEach(() => {
  explicar.mockReset().mockResolvedValue({
    semantica: "A empresa violou o segredo industrial.",
    termos: ["violação de segredo industrial", "CPC art. 473, § 3º"],
  });
});

describe("Como esta busca foi feita", () => {
  it("começa fechado e só pede a explicação ao abrir", async () => {
    render(<ComoFoiBuscado estrutura={estrutura} filtro={null} />);
    expect(explicar).not.toHaveBeenCalled();
    expect(screen.queryByText("Busca semântica")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Como esta busca foi feita/ }));

    expect(await screen.findByText("“A empresa violou o segredo industrial.”")).toBeInTheDocument();
    expect(screen.getByText("violação de segredo industrial")).toBeInTheDocument();
    expect(screen.getByText("CPC art. 473, § 3º")).toBeInTheDocument();
    expect(explicar).toHaveBeenCalledTimes(1);
  });

  it("sem filtro restrito não mostra a linha do filtro", async () => {
    render(<ComoFoiBuscado estrutura={estrutura} filtro={null} />);
    await userEvent.click(screen.getByRole("button", { name: /Como esta busca foi feita/ }));
    await screen.findByText("Busca semântica");
    expect(screen.queryByText("Filtro restrito")).not.toBeInTheDocument();
  });

  it("com filtro mostra os dispositivos, as expressões e quantas decisões passaram", async () => {
    render(<ComoFoiBuscado estrutura={estrutura} filtro={{ itens: ["CPC art. 473, § 3º", "“dano moral coletivo”"], total: 82 }} />);
    await userEvent.click(screen.getByRole("button", { name: /Como esta busca foi feita/ }));
    expect(await screen.findByText("Filtro restrito")).toBeInTheDocument();
    expect(screen.getByText("“dano moral coletivo”")).toBeInTheDocument();
    expect(screen.getByText(/82 de 69\.349 decisões passaram; só elas foram ordenadas\./)).toBeInTheDocument();
  });

  it("se a explicação falhar, avisa sem quebrar", async () => {
    explicar.mockRejectedValue(new Error("x"));
    render(<ComoFoiBuscado estrutura={estrutura} filtro={null} />);
    await userEvent.click(screen.getByRole("button", { name: /Como esta busca foi feita/ }));
    expect(await screen.findByText(/Não foi possível carregar como a busca foi feita/)).toBeInTheDocument();
  });
});
