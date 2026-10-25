import { render, screen } from "@testing-library/react";
import { Chip } from "@/components/ui/chip";

describe("Chip", () => {
  it("renderiza o texto passado como children", () => {
    render(<Chip>NR-15</Chip>);
    expect(screen.getByText("NR-15")).toBeInTheDocument();
  });

  it("aplica classes diferentes por tom sem quebrar a renderização", () => {
    const { rerender } = render(<Chip tone="amber">Benzeno</Chip>);
    expect(screen.getByText("Benzeno").className).toMatch(/FBF4EC/i);

    rerender(<Chip tone="blue">CLT 192</Chip>);
    expect(screen.getByText("CLT 192")).toBeInTheDocument();
  });

  it("usa fonte menor no tamanho 'sm'", () => {
    render(<Chip size="sm">Entidade</Chip>);
    expect(screen.getByText("Entidade")).toHaveStyle({ fontSize: "12.1px" });
  });
});
