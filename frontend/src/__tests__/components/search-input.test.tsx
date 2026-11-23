import { act, createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchInput, type SearchInputHandle } from "@/components/home/search-input";

const campo = () => screen.getByPlaceholderText(/Descreva sua tese/);
const pdf = (kb: number, nome = "autos.pdf") => new File([new Uint8Array(kb * 1024)], nome, { type: "application/pdf" });
const anexar = (arquivo: File) =>
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [arquivo] } });

describe("SearchInput", () => {
  it("Enter envia a consulta sem espaços nas pontas; Shift+Enter não envia", async () => {
    const onSubmit = jest.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    await userEvent.type(campo(), "  horas extras  {Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.type(campo(), "{Enter}");
    expect(onSubmit).toHaveBeenCalledWith({ query: "horas extras", hasFile: false, file: null, fileName: null, fileBytes: null });
  });

  it("sem texto nem arquivo, o botão fica desabilitado e nada é enviado", async () => {
    const onSubmit = jest.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    expect(screen.getByRole("button", { name: "Pesquisar" })).toBeDisabled();
    await userEvent.type(campo(), "   {Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("PDF anexado mostra nome e tamanho, e sem texto a consulta vira o nome do arquivo", async () => {
    const onSubmit = jest.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    const arquivo = pdf(2048);
    anexar(arquivo);
    expect(screen.getByText("autos.pdf")).toBeInTheDocument();
    expect(screen.getByText("2.0 MB")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pesquisar" }));
    expect(onSubmit).toHaveBeenCalledWith({ query: "autos.pdf", hasFile: true, file: arquivo, fileName: "autos.pdf", fileBytes: arquivo.size });
  });

  it("arquivo pequeno aparece em KB, e o X remove o anexo", async () => {
    render(<SearchInput />);
    anexar(pdf(3, "peca.pdf"));
    expect(screen.getByText("3 KB")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remover arquivo" }));
    expect(screen.queryByText("peca.pdf")).not.toBeInTheDocument();
  });

  it("change sem arquivo não anexa nada", () => {
    render(<SearchInput />);
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [] } });
    expect(screen.getByRole("button", { name: "Pesquisar" })).toBeDisabled();
  });

  it("desabilitado: campo e anexar bloqueados", () => {
    render(<SearchInput disabled />);
    expect(campo()).toBeDisabled();
    expect(screen.getByTitle("Enviar PDF")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Pesquisar" })).toBeDisabled();
  });

  it("Anexar PDF abre o seletor de arquivo", async () => {
    render(<SearchInput />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clique = jest.spyOn(input, "click");
    await userEvent.click(screen.getByTitle("Enviar PDF"));
    expect(clique).toHaveBeenCalled();
  });

  it("handle: preencher põe o texto e o foco no campo; clearAndReopenFile tira o anexo e reabre o seletor", async () => {
    const ref = createRef<SearchInputHandle>();
    jest.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
    render(<SearchInput ref={ref} />);
    act(() => ref.current!.preencher("dano moral"));
    expect(campo()).toHaveValue("dano moral");
    expect(campo()).toHaveFocus();

    anexar(pdf(1));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const clique = jest.spyOn(input, "click");
    act(() => ref.current!.clearAndReopenFile());
    expect(screen.queryByText("autos.pdf")).not.toBeInTheDocument();
    expect(clique).toHaveBeenCalled();
  });
});
