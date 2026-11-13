import { render, screen, within } from "@testing-library/react";
import { GuiaPage } from "@/components/guia/guia-page";
import { ComoUsarLink } from "@/components/home/como-usar-link";

describe("GuiaPage", () => {
  it("mostra o título e o tamanho do acervo", () => {
    render(<GuiaPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Como tirar o melhor do JuriSight" })).toBeInTheDocument();
    expect(screen.getAllByText(/69\.349/).length).toBeGreaterThan(0);
  });

  it("a trilha é uma lista ordenada de 7 etapas", () => {
    render(<GuiaPage />);
    const trilha = screen.getByRole("list", { name: "Etapas" });
    expect(trilha.tagName).toBe("OL");
    const itens = within(trilha).getAllByRole("listitem").filter((li) => li.parentElement === trilha);
    expect(itens).toHaveLength(7);
    expect(itens[0]).toHaveTextContent("Conte o caso");
    expect(itens[6]).toHaveTextContent("Limites desta versão");
  });

  it("usa os nomes das três buscas", () => {
    render(<GuiaPage />);
    for (const nome of ["Filtro restrito", "Busca semântica", "Busca por termos"]) {
      expect(screen.getAllByText(new RegExp(nome)).length).toBeGreaterThan(0);
    }
  });

  it("termina levando à tela inicial", () => {
    render(<GuiaPage />);
    expect(screen.getByRole("link", { name: /Ir para a tela inicial/ })).toHaveAttribute("href", "/");
  });

  it("ícones são decorativos", () => {
    const { container } = render(<GuiaPage />);
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(10);
    svgs.forEach((s) => expect(s.getAttribute("aria-hidden")).toBe("true"));
  });
});

describe("ComoUsarLink", () => {
  it("leva ao guia", () => {
    render(<ComoUsarLink />);
    expect(screen.getByRole("link", { name: /Como usar/ })).toHaveAttribute("href", "/guia");
  });
});
