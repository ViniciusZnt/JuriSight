import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ParecerPesquisa } from "@/components/resultados/parecer-pesquisa";
import { emptyEstrutura, explicarBusca, type ResultCard, type RespostaIA } from "@/lib/api";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), explicarBusca: jest.fn() }));
const explicar = explicarBusca as jest.Mock;

const estrutura = { ...emptyEstrutura(), tese_central: "A empresa não paga horas extras ao motorista." };
const card = (id: string, tribunal: string, turma: string) => ({ id, tribunal, turma, numero_processo: `0-${id}` } as unknown as ResultCard);
const ordem = [card("a", "TRT7", "2ª Turma"), card("b", "TRT1", "9ª Turma"), card("c", "TRT22", "Segunda Turma")];

const resposta: RespostaIA = {
  frases: [
    { tipo: "resposta", texto: "Sim. A empresa deve pagar horas extras se não comprovar o controle.", citacoes: [1, 2] },
    { tipo: "fundamento", texto: "Os registros de tacógrafo não substituem os controles de ponto.", citacoes: [1] },
    { tipo: "fundamento", texto: "O controle indireto afasta a exceção do art. 62, I, da CLT.", citacoes: [2, 3] },
    { tipo: "base_legal", texto: "CLT, art. 74, § 2º: a falta dos registros gera presunção de veracidade", citacoes: [1, 3] },
    { tipo: "prova", texto: "Para o pedido, é preciso provar: controle de jornada; horas trabalhadas", citacoes: [1, 2] },
    { tipo: "divergencia", texto: "As que negaram partiram de controles de ponto válidos.", citacoes: [3] },
  ],
  posicoes: [],
};
const ok = { chave: "k", vazia: false, estado: { status: "ok" as const, resposta } };

beforeEach(() => {
  explicar.mockReset().mockResolvedValue({
    semantica: "A empresa não paga horas extras ao motorista.",
    termos: ["horas extras", "rastreador", "tacógrafo", "motorista", "ausência de remuneração"],
  });
  localStorage.clear();
});

const renderParecer = (extra: Partial<React.ComponentProps<typeof ParecerPesquisa>> = {}) =>
  render(
    <ParecerPesquisa
      estrutura={estrutura}
      filtro={{ itens: ["horas extras", "motorista"], total: 1104 }}
      resposta={ok}
      ordem={ordem}
      onIr={jest.fn()}
      {...extra}
    />
  );

describe("ParecerPesquisa", () => {
  it("abre com a pesquisa: filtro com o total do acervo, busca semântica e termos", async () => {
    renderParecer();
    const faixa = screen.getByRole("region", { name: "Como esta busca foi feita" });
    expect(within(faixa).getByText("horas extras")).toBeInTheDocument();
    expect(within(faixa).getByText("1.104")).toBeInTheDocument();
    expect(within(faixa).getByText("de 69.349 decisões")).toBeInTheDocument();
    expect(await within(faixa).findByText("A empresa não paga horas extras ao motorista.")).toBeInTheDocument();
    expect(within(faixa).getByText("tacógrafo")).toBeInTheDocument();
    await userEvent.click(within(faixa).getByRole("button", { name: "+1" }));
    expect(within(faixa).getByText("ausência de remuneração")).toBeInTheDocument();
  });

  it("marcadores de semântica e termos nas cores da paleta", async () => {
    renderParecer();
    const sem = await screen.findByText("Busca semântica");
    const ter = screen.getByText("Busca por termos");
    expect(sem.querySelector("span")?.className).toContain("#B6A5F0");
    expect(ter.querySelector("span")?.className).toContain("#5FCFC4");
  });

  it("sem filtro restrito não mostra a coluna do filtro", async () => {
    renderParecer({ filtro: null });
    await screen.findByText("Busca semântica");
    expect(screen.queryByText("Filtro restrito")).not.toBeInTheDocument();
  });

  it("resposta com o veredito separado e o resto da frase", () => {
    renderParecer();
    expect(screen.getByText("Sim.")).toBeInTheDocument();
    expect(screen.getByText(/A empresa deve pagar horas extras se não comprovar o controle\./)).toBeInTheDocument();
  });

  it("cada fundamento termina com o órgão das decisões citadas, que leva ao card", async () => {
    const onIr = jest.fn();
    renderParecer({ onIr });
    expect(screen.getByRole("link", { name: "9ª Turma do TRT-1 e 2ª Turma do TRT-22" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "2ª Turma do TRT-7" }));
    expect(onIr).toHaveBeenCalledWith("a");
  });

  it("o que provar, base legal e atenção em linhas próprias", () => {
    renderParecer();
    expect(screen.getByText("Controle de jornada")).toBeInTheDocument();
    expect(screen.getByText("Horas trabalhadas")).toBeInTheDocument();
    expect(screen.getByText("CLT, art. 74, § 2º")).toBeInTheDocument();
    expect(screen.getByText("Atenção")).toBeInTheDocument();
    expect(screen.getByText(/As que negaram partiram de controles de ponto válidos\./)).toBeInTheDocument();
  });

  it("enquanto gera, mostra o carregamento na linha da resposta", () => {
    renderParecer({ resposta: { chave: "k", vazia: false, estado: { status: "carregando" } } });
    expect(screen.getByLabelText("Gerando a resposta a partir das decisões…")).toBeInTheDocument();
  });

  it("sem decisões, explica por que não há resposta", () => {
    renderParecer({ resposta: { chave: "k", vazia: true, estado: { status: "carregando" } }, semResposta: "Sem decisões no filtro restrito, a resposta não é gerada." });
    expect(screen.getByText("Sem decisões no filtro restrito, a resposta não é gerada.")).toBeInTheDocument();
  });

  it("erro na resposta aparece sem derrubar a pesquisa", async () => {
    renderParecer({ resposta: { chave: "k", vazia: false, estado: { status: "erro", mensagem: "OpenAI fora" } } });
    expect(screen.getByText(/Resposta gerada indisponível: OpenAI fora/)).toBeInTheDocument();
    expect(await screen.findByText("A empresa não paga horas extras ao motorista.")).toBeInTheDocument();
  });
});
