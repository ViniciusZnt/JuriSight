import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "@/components/app-shell";

jest.mock("@/components/sidebar", () => ({ Sidebar: () => <nav>menu lateral</nav> }));

const largura = (px: number) => Object.defineProperty(window, "innerWidth", { configurable: true, value: px });

describe("AppShell", () => {
  it("no desktop o botão recolhe e expande a sidebar", async () => {
    largura(1280);
    render(<AppShell><p>conteúdo</p></AppShell>);
    expect(screen.getByText("conteúdo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Recolher menu" }));
    expect(screen.getByRole("button", { name: "Expandir menu" })).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(screen.getByRole("button", { name: "Expandir menu" }));
    expect(screen.getByRole("button", { name: "Recolher menu" })).toHaveAttribute("aria-expanded", "true");
  });

  it("no celular o botão abre a sidebar por cima, e o fundo escuro fecha", async () => {
    largura(375);
    render(<AppShell><p>conteúdo</p></AppShell>);
    expect(screen.queryByRole("button", { name: "Fechar menu lateral" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Recolher menu" }));
    await userEvent.click(screen.getByRole("button", { name: "Fechar menu lateral" }));
    expect(screen.queryByRole("button", { name: "Fechar menu lateral" })).not.toBeInTheDocument();
  });
});
