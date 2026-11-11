import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResumoDecisoes } from "@/components/resultados/resumo-decisoes";
import type { ResultCard } from "@/lib/api";
import type { Sintese } from "@/lib/sintese";

const card = (id: string, tribunal: string, turma: string, data: string) =>
  ({ id, tribunal, turma, data_julgamento: data } as unknown as ResultCard);

const sintese: Sintese = {
  abertura: "As decisões se dividem.",
  tendencia: "Das 20 decisões, 9 favorecem o trabalhador, 1 a empresa e 10 sem lado claro.",
  base: [
    { rotulo: "Súmula 338 do TST", ids: ["a", "b", "c", "d", "e", "f"] },
    { rotulo: "art. 62 da CLT", ids: ["a", "b"] },
  ],
  trabalhador: ["a", "b"],
  empresa: ["k"],
};
const porId = new Map([
  ["a", card("a", "TRT6", "4ª Turma", "2025-02-18")],
  ["b", card("b", "TRT4", "1ª Turma", "2025-05-09")],
  ["k", card("k", "TRT6", "3ª Turma", "2025-09-03")],
]);
const ranks = new Map([["a", 1], ["b", 2], ["k", 11]]);

function renderResumo(extra: Partial<React.ComponentProps<typeof ResumoDecisoes>> = {}) {
  const props: React.ComponentProps<typeof ResumoDecisoes> = {
    total: 1104,
    descricao: "decisões do acervo",
    grupos: [{ verbo: "contêm", itens: ["horas extras", "motorista"] }],
    nota: "mostrando as 20 mais relevantes",
    tese: "A empresa não paga horas extras ao motorista.",
    desfechos: { favorable: 9, unfavorable: 1, neutral: 10 },
    mostradas: 20,
    filtro: "all",
    onFiltro: jest.fn(),
    sintese,
    porId,
    ranks,
    citacao: null,
    onCitacao: jest.fn(),
    onIr: jest.fn(),
    ...extra,
  };
  render(<ResumoDecisoes {...props} />);
  return props;
}

describe("ResumoDecisoes", () => {
  it("mostra o total, os termos do filtro e a tese no topo", () => {
    renderResumo();
    expect(screen.getByText("1.104")).toBeInTheDocument();
    expect(screen.getByText("horas extras")).toBeInTheDocument();
    expect(screen.getByText("motorista")).toBeInTheDocument();
    expect(screen.getByText(/A empresa não paga horas extras ao motorista\./)).toBeInTheDocument();
  });

  it("as placas de desfecho filtram e, clicadas de novo, voltam para todas", async () => {
    const p = renderResumo();
    await userEvent.click(screen.getByRole("button", { name: /9\s*favoráveis/ }));
    expect(p.onFiltro).toHaveBeenCalledWith("favorable");
  });

  it("placa já ativa volta o filtro para todas", async () => {
    const p = renderResumo({ filtro: "unfavorable" });
    await userEvent.click(screen.getByRole("button", { name: /1\s*desfavorável/ }));
    expect(p.onFiltro).toHaveBeenCalledWith("all");
  });

  it("base citada filtra pelos que a citam", async () => {
    const p = renderResumo();
    await userEvent.click(screen.getByRole("button", { name: /Súmula 338 do TST/ }));
    expect(p.onCitacao).toHaveBeenCalledWith("Súmula 338 do TST");
  });

  it("precedentes para citar levam ao card", async () => {
    const p = renderResumo();
    expect(screen.getByText("Favorável ao trabalhador")).toBeInTheDocument();
    expect(screen.getByText("Favorável à empresa")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /#11.*TRT6 · 3ª Turma/ }));
    expect(p.onIr).toHaveBeenCalledWith("k");
  });

  it("sem resultados mostra só o topo", () => {
    renderResumo({ total: 0, sintese: null, mostradas: 0, nota: "Abra a busca livre abaixo para ver decisões parecidas." });
    expect(screen.getByText(/Abra a busca livre abaixo/)).toBeInTheDocument();
    expect(screen.queryByText("Panorama")).not.toBeInTheDocument();
  });
});
