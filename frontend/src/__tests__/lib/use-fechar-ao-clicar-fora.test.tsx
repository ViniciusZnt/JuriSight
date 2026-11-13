import { fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { useFecharAoClicarFora } from "@/lib/use-fechar-ao-clicar-fora";

function Caixa({ aberto, fechar, comEsc }: { aberto: boolean; fechar: () => void; comEsc?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useFecharAoClicarFora(ref, aberto, fechar, comEsc);
  return (
    <div>
      <div ref={ref}>dentro</div>
      <p>fora</p>
    </div>
  );
}

describe("useFecharAoClicarFora", () => {
  it("fecha ao clicar fora, mas não ao clicar dentro", () => {
    const fechar = jest.fn();
    render(<Caixa aberto fechar={fechar} />);
    fireEvent.mouseDown(screen.getByText("dentro"));
    expect(fechar).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByText("fora"));
    expect(fechar).toHaveBeenCalledTimes(1);
  });

  it("não escuta nada enquanto está fechado", () => {
    const fechar = jest.fn();
    render(<Caixa aberto={false} fechar={fechar} />);
    fireEvent.mouseDown(screen.getByText("fora"));
    expect(fechar).not.toHaveBeenCalled();
  });

  it("Esc só fecha quando pedido", () => {
    const fechar = jest.fn();
    const { rerender } = render(<Caixa aberto fechar={fechar} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(fechar).not.toHaveBeenCalled();
    rerender(<Caixa aberto fechar={fechar} comEsc />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(fechar).toHaveBeenCalledTimes(1);
  });
});
