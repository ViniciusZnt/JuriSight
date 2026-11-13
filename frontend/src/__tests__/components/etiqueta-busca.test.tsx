import { render, screen } from "@testing-library/react";
import { EtiquetaBusca } from "@/components/ui/etiqueta-busca";

describe("EtiquetaBusca", () => {
  it("mostra o nome da busca na cor dela", () => {
    render(<EtiquetaBusca busca="termos" />);
    const el = screen.getByText("Busca por termos");
    expect(el.className).toContain("#E6F5F3");
  });

  it("semântica em violeta", () => {
    render(<EtiquetaBusca busca="semantica" />);
    expect(screen.getByText("Busca semântica").className).toContain("#F1EDFC");
  });
});
