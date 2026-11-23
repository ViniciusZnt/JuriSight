import { fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { useFecharAoClicarFora } from "@/lib/use-fechar-ao-clicar-fora";

function Caixa({ aberto, fechar, comEsc }: { aberto: boolean; fechar: () => void; comEsc?: boolean | (() => void) }) {
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

  it("com uma função em `comEsc`, o Esc chama ela no lugar de `fechar`; outras teclas não fazem nada", () => {
    const fechar = jest.fn();
    const aoEsc = jest.fn();
    render(<Caixa aberto fechar={fechar} comEsc={aoEsc} />);
    fireEvent.keyDown(document, { key: "Enter" });
    expect(aoEsc).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(aoEsc).toHaveBeenCalledTimes(1);
    expect(fechar).not.toHaveBeenCalled();
  });

  it("chama o `fechar` mais recente, sem refazer os listeners", () => {
    const antigo = jest.fn();
    const novo = jest.fn();
    const { rerender } = render(<Caixa aberto fechar={antigo} />);
    rerender(<Caixa aberto fechar={novo} />);
    fireEvent.mouseDown(screen.getByText("fora"));
    expect(antigo).not.toHaveBeenCalled();
    expect(novo).toHaveBeenCalledTimes(1);
  });
});
