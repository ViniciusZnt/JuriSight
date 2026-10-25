import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Bookmark } from "lucide-react";
import { ActionButton } from "@/components/ui/action-button";

describe("ActionButton", () => {
  it("renderiza o rótulo passado", () => {
    render(<ActionButton icon={Bookmark} label="Salvar" />);
    expect(screen.getByRole("button", { name: "Salvar" })).toBeInTheDocument();
  });

  it("chama onClick ao ser clicado", async () => {
    const onClick = jest.fn();
    render(<ActionButton icon={Bookmark} label="Salvar" onClick={onClick} />);
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("preenche o ícone quando iconFill está ativo (estado 'salvo')", () => {
    render(<ActionButton icon={Bookmark} label="Salvo" iconFill />);
    const icon = screen.getByRole("button", { name: "Salvo" }).querySelector("svg");
    expect(icon).toHaveAttribute("fill", "currentColor");
  });
});
