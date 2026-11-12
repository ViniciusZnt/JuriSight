import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepIndicator } from "@/components/step-indicator";

describe("StepIndicator", () => {
  it("mostra os três passos do fluxo de consulta", () => {
    render(<StepIndicator current={0} />);
    expect(screen.getByText("Documento enviado")).toBeInTheDocument();
    expect(screen.getByText("Revisão de contexto")).toBeInTheDocument();
    expect(screen.getByText("Jurisprudências")).toBeInTheDocument();
  });

  it("troca o rótulo do primeiro passo no modo manual (UC02 — sem PDF)", () => {
    render(<StepIndicator current={0} manual />);
    expect(screen.queryByText("Documento enviado")).not.toBeInTheDocument();
    expect(screen.getByText("Consulta iniciada")).toBeInTheDocument();
  });

  it("não altera os passos seguintes no modo manual", () => {
    render(<StepIndicator current={1} manual />);
    expect(screen.getByText("Revisão de contexto")).toBeInTheDocument();
    expect(screen.getByText("Jurisprudências")).toBeInTheDocument();
  });
});

describe("StepIndicator — editar a revisão", () => {
  it("com onEditarRevisao, mostra um lápis ao lado de Revisão de contexto que volta à revisão", async () => {
    const onEditar = jest.fn();
    render(<StepIndicator current={2} onEditarRevisao={onEditar} />);
    await userEvent.click(screen.getByRole("button", { name: "Editar a revisão de contexto" }));
    expect(onEditar).toHaveBeenCalled();
  });

  it("sem onEditarRevisao, não há lápis", () => {
    render(<StepIndicator current={1} />);
    expect(screen.queryByRole("button", { name: "Editar a revisão de contexto" })).not.toBeInTheDocument();
  });

  it("o passo atual usa anel (ring) em vez de sombra, para o destaque acompanhar o círculo", () => {
    render(<StepIndicator current={2} />);
    const atual = screen.getByText("Jurisprudências").previousElementSibling as HTMLElement;
    expect(atual.className).toMatch(/ring-4/);
    expect(atual.className).not.toMatch(/shadow-\[0_0_10px/);
  });
});
