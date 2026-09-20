import { render, screen } from "@testing-library/react";
import { OutcomeBadge } from "@/components/ui/outcome-badge";

describe("OutcomeBadge", () => {
  it("mostra 'Favorável' para provimento favorável", () => {
    render(<OutcomeBadge outcome="favorable" />);
    expect(screen.getByText("Favorável")).toBeInTheDocument();
  });

  it("mostra 'Desfavorável' para provimento desfavorável", () => {
    render(<OutcomeBadge outcome="unfavorable" />);
    expect(screen.getByText("Desfavorável")).toBeInTheDocument();
  });

  it("mostra 'Neutro' para provimento neutro", () => {
    render(<OutcomeBadge outcome="neutral" />);
    expect(screen.getByText("Neutro")).toBeInTheDocument();
  });

  it("adiciona o sufixo opcional ao lado do rótulo", () => {
    render(<OutcomeBadge outcome="favorable" suffix=" à tese" />);
    expect(screen.getByText(/Favorável\s*à tese/)).toBeInTheDocument();
  });
});
