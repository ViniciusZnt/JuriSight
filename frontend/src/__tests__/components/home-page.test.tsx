import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HomePage } from "@/components/home/home-page";
import { ApiError, enrich } from "@/lib/api";

const push = jest.fn();
const create = jest.fn().mockResolvedValue(undefined);
const setEnrichResult = jest.fn();
const atualizarUso = jest.fn();

jest.mock("next/navigation", () => ({ useRouter: () => ({ push, prefetch: jest.fn() }) }));
jest.mock("@/lib/conversations", () => ({ useConversations: () => ({ create }) }));
jest.mock("@/lib/search-session", () => ({ useSearchSession: () => ({ setEnrichResult }) }));
jest.mock("@/lib/uso-diario", () => ({ useUsoDiario: () => ({ atualizar: atualizarUso }) }));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), enrich: jest.fn() }));

const enrichMock = enrich as jest.Mock;
const estrutura = { tese: "t" };
const resposta = (extra: object = {}) => ({
  estrutura, pdf_extraido: null, aviso: null, dispositivos_ia: ["clt_art_59"],
  expressoes_sugeridas: [], dispositivos_sugeridos: [], ...extra,
});

const campo = () => screen.getByPlaceholderText(/Descreva sua tese/);
const anexar = (nome: string, bytes: number) => {
  const arquivo = new File(["x"], nome, { type: "application/pdf" });
  Object.defineProperty(arquivo, "size", { value: bytes });
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [arquivo] } });
  return arquivo;
};
const pesquisar = () => userEvent.click(screen.getByRole("button", { name: "Pesquisar" }));

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(console, "error").mockImplementation(() => {});
});

describe("HomePage", () => {
  it("consulta só com texto: guarda o resultado, cria a conversa e vai para a revisão manual", async () => {
    enrichMock.mockResolvedValue(resposta());
    render(<HomePage />);
    await userEvent.type(campo(), "horas extras{Enter}");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/revisao?modo=manual"));
    expect(enrichMock).toHaveBeenCalledWith({ pdf: null, intencao: "horas extras" });
    expect(setEnrichResult).toHaveBeenCalledWith(expect.objectContaining({ estrutura, hasFile: false, dispositivosIa: ["clt_art_59"] }));
    expect(create).toHaveBeenCalledWith("horas extras");
    expect(atualizarUso).toHaveBeenCalled();
  });

  it("com PDF lido vai para a revisão normal; PDF grande mostra o aviso de documento extenso enquanto espera", async () => {
    let resolver: (v: unknown) => void = () => {};
    enrichMock.mockReturnValue(new Promise((r) => (resolver = r)));
    render(<HomePage />);
    anexar("autos.pdf", 9 * 1024 * 1024);
    await pesquisar();
    expect(screen.getByText("Documento extenso detectado")).toBeInTheDocument();
    await act(async () => resolver(resposta({ pdf_extraido: true })));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/revisao"));
    expect(screen.queryByText("Documento extenso detectado")).not.toBeInTheDocument();
  });

  it("enquanto espera um arquivo comum, mostra o aviso de análise", async () => {
    enrichMock.mockReturnValue(new Promise(() => {}));
    render(<HomePage />);
    await userEvent.type(campo(), "dano moral{Enter}");
    expect(screen.getByText(/Analisando sua consulta/)).toBeInTheDocument();
  });

  it("PDF acima de 20 MB é recusado antes de enviar, e o aviso fecha", async () => {
    render(<HomePage />);
    anexar("enorme.pdf", 21 * 1024 * 1024);
    await pesquisar();
    expect(screen.getByText(/passa do limite de 20 MB/)).toBeInTheDocument();
    expect(enrichMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByText(/passa do limite/)).not.toBeInTheDocument();
  });

  it("erro da API mostra a mensagem dela; erro qualquer mostra a genérica", async () => {
    enrichMock.mockRejectedValueOnce(new ApiError("Limite diário atingido.", 429));
    render(<HomePage />);
    await userEvent.type(campo(), "x{Enter}");
    expect(await screen.findByText("Limite diário atingido.")).toBeInTheDocument();

    enrichMock.mockRejectedValueOnce(new Error("rede"));
    await userEvent.type(campo(), "{Enter}");
    expect(await screen.findByText(/Não foi possível processar a consulta/)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  describe("PDF sem texto (FA02)", () => {
    const fa02 = async () => {
      enrichMock.mockResolvedValue(resposta({ pdf_extraido: false, aviso: "PDF escaneado." }));
      render(<HomePage />);
      anexar("scan.pdf", 1024);
      await userEvent.type(campo(), "estabilidade");
      await pesquisar();
      expect(await screen.findByText("PDF escaneado.")).toBeInTheDocument();
      expect(screen.getByText(/extrair texto de .scan\.pdf./)).toBeInTheDocument();
    };

    it("continuar sem o PDF corrige a sessão (sem arquivo) e vai para a revisão manual", async () => {
      await fa02();
      setEnrichResult.mockClear();
      await userEvent.click(screen.getByRole("button", { name: /Continuar sem o PDF/ }));
      await waitFor(() => expect(push).toHaveBeenCalledWith("/revisao?modo=manual"));
      expect(setEnrichResult).toHaveBeenCalledWith(expect.objectContaining({ hasFile: false, fileName: null, pdfExtraido: false, dispositivosIa: ["clt_art_59"] }));
      expect(create).toHaveBeenCalledWith("estabilidade");
    });

    it("reenviar tira o anexo e reabre o seletor; fechar some com o aviso", async () => {
      await fa02();
      const clique = jest.spyOn(document.querySelector('input[type="file"]') as HTMLInputElement, "click");
      await userEvent.click(screen.getByRole("button", { name: /Reenviar arquivo/ }));
      expect(clique).toHaveBeenCalled();
      expect(screen.queryByText("PDF escaneado.")).not.toBeInTheDocument();
    });

    it("o X fecha o aviso sem navegar", async () => {
      await fa02();
      await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
      expect(screen.queryByText("PDF escaneado.")).not.toBeInTheDocument();
      expect(push).not.toHaveBeenCalled();
    });

    it("sem aviso do backend nem nome de arquivo, usa os textos padrão", async () => {
      enrichMock.mockResolvedValue(resposta({ pdf_extraido: false, aviso: null }));
      render(<HomePage />);
      await userEvent.type(campo(), "x{Enter}");
      expect(await screen.findByText("Não foi possível extrair texto do PDF enviado.")).toBeInTheDocument();
      expect(screen.getByText(/arquivo enviado/)).toBeInTheDocument();
    });
  });

  it("um exemplo preenche o campo sem pesquisar", async () => {
    jest.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      cb(0);
      return 0;
    });
    render(<HomePage />);
    await userEvent.click(screen.getByRole("button", { name: /Rescisão indireta/ }));
    expect((campo() as HTMLTextAreaElement).value).toContain("FGTS");
    expect(enrichMock).not.toHaveBeenCalled();
  });
});
