import { render, screen } from "@testing-library/react";
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
