import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResumoDecisoes } from "@/components/resultados/resumo-decisoes";
import type { Sintese } from "@/lib/sintese";

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

function renderResumo(extra: Partial<React.ComponentProps<typeof ResumoDecisoes>> = {}) {
  const props: React.ComponentProps<typeof ResumoDecisoes> = {
    total: 1104,
    descricao: "decisões do acervo",
    grupos: [{ verbo: "contêm", itens: ["horas extras", "motorista"] }],
    nota: null,
    tese: "A empresa não paga horas extras ao motorista.",
    desfechos: { favorable: 9, unfavorable: 1, neutral: 10 },
    mostradas: 20,
    sintese,
    citacao: null,
    onCitacao: jest.fn(),
    acoes: <button>Refinar</button>,
    ...extra,
  };
  render(<ResumoDecisoes {...props} />);
  return props;
}

describe("ResumoDecisoes", () => {
  it("mostra o total, os termos exigidos, a tese e as ações da consulta na faixa", () => {
    renderResumo();
    expect(screen.getByText("1.104")).toBeInTheDocument();
    expect(screen.getByText("horas extras")).toBeInTheDocument();
    expect(screen.getByText("motorista")).toBeInTheDocument();
    expect(screen.getByText(/A empresa não paga horas extras ao motorista\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refinar" })).toBeInTheDocument();
  });

  it("panorama diz de quantas decisões fala, o veredito e os números uma vez só", () => {
    renderResumo();
    expect(screen.getByText("Panorama das 20 mais relevantes")).toBeInTheDocument();
    expect(screen.getByText("As decisões se dividem")).toBeInTheDocument();
    expect(screen.getByText(/favorecem o trabalhador/)).toBeInTheDocument();
  });

  it("não tem mais a seção Para citar nem as placas de desfecho", () => {
    renderResumo();
    expect(screen.queryByText("Para citar")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /favoráveis/ })).not.toBeInTheDocument();
  });

  it("base citada filtra pelos que a citam e desmarca ao clicar de novo", async () => {
    const p = renderResumo();
    await userEvent.click(screen.getByRole("button", { name: /Súmula 338 do TST/ }));
    expect(p.onCitacao).toHaveBeenCalledWith("Súmula 338 do TST");
  });

  it("sem resultados mostra só a faixa com a nota", () => {
    renderResumo({ total: 0, sintese: null, mostradas: 0, nota: "Abra a busca livre abaixo para ver decisões parecidas." });
    expect(screen.getByText(/Abra a busca livre abaixo/)).toBeInTheDocument();
    expect(screen.queryByText(/Panorama/)).not.toBeInTheDocument();
  });
});
