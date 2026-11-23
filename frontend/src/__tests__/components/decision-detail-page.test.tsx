import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DecisionDetailPage } from "@/components/decisao/decision-detail-page";
import { ApiError, getDocument, type DocumentoDetalhe, type EstruturaArgumentativa } from "@/lib/api";
import { copiarTexto } from "@/lib/utils";

const push = jest.fn();
const toggle = jest.fn();
let salvo = false;
let sessao: { estrutura: EstruturaArgumentativa | null; resultados: { id: string; score_rrf: number }[] | null } = {
  estrutura: null,
  resultados: null,
};

jest.mock("next/navigation", () => ({ useRouter: () => ({ push, prefetch: jest.fn() }) }));
jest.mock("@/lib/saved", () => ({ useSaved: () => ({ isSaved: () => salvo, toggle }) }));
jest.mock("@/lib/search-session", () => ({ useSearchSession: () => sessao }));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), getDocument: jest.fn() }));
jest.mock("@/lib/utils", () => ({ ...jest.requireActual("@/lib/utils"), copiarTexto: jest.fn().mockResolvedValue(undefined) }));

const getDocumentMock = getDocument as jest.Mock;
const copiarMock = copiarTexto as jest.Mock;

const estrutura: EstruturaArgumentativa = {
  pedido_principal: "adicional", agente_nocivo: ["ruído"], violacoes: [], normas: ["NR-15", "NR-99"],
  tese_central: "t", dispositivos: [], expressoes: [], tribunais: [], fase: null,
};

const documento = (extra: Partial<DocumentoDetalhe> = {}): DocumentoDetalhe => ({
  id: "d1", id_documento: "x", tipo_documento: "ACORDAO" as DocumentoDetalhe["tipo_documento"], hierarquia_categoria: 1,
  data_filtro: null, numero_processo: "0001234-56.2024.5.04.0001", tribunal: "TRT4", classe_processo: "Recurso Ordinário",
  sigla_classe: "ROT", relator: "Fulana de Tal", turma: "1ª Turma", gabinete: "", data_julgamento: "2025-03-10",
  data_juntada: null, cabecalho: "",
  ementa: "ADICIONAL DE INSALUBRIDADE. RUÍDO. Exposição acima da NR-15 sem EPI eficaz.",
  relatorio: "Relatório do caso.",
  fundamentacao: "Fundamentos breves.",
  acordao: `${"Texto do inteiro teor. ".repeat(250)}ACORDAM os magistrados em dar provimento ao recurso.`,
  votos: "Voto vencido.",
  possui_ementa: true, referencia_legislativa: ["clt_art_189"], provimento: "PROVIDO" as DocumentoDetalhe["provimento"],
  link_original: "https://exemplo.invalid/doc", classificacao_provimento: null,
  ...extra,
});

beforeEach(() => {
  jest.clearAllMocks();
  salvo = false;
  sessao = { estrutura: null, resultados: null };
});

describe("DecisionDetailPage", () => {
  it("mostra carregando e depois o documento, com seções, dispositivo e fonte", async () => {
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    expect(screen.getByText("Carregando decisão…")).toBeInTheDocument();
    expect(await screen.findByText("ADICIONAL DE INSALUBRIDADE. RUÍDO.")).toBeInTheDocument();
    expect(getDocumentMock).toHaveBeenCalledWith("d1");
    for (const t of ["Ementa", "Relatório", "Fundamentação", "Dispositivo", "Inteiro teor", "Votos", "Dispositivos legais citados"]) {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("Rel. Fulana de Tal")).toBeInTheDocument();
    expect(screen.getByText("Origem: TRT4")).toBeInTheDocument();
    expect(screen.getByText(/Na fonte, esta seção veio curta/)).toBeInTheDocument();
    expect(screen.getByText("Sem uma consulta ativa nesta sessão para comparar com este documento.")).toBeInTheDocument();
    expect(document.querySelector('a[href="https://exemplo.invalid/doc"]')).not.toBeNull();
  });

  it("com consulta na sessão mostra relevância e os termos do contexto encontrados", async () => {
    sessao = { estrutura, resultados: [{ id: "outro", score_rrf: 0.9 }, { id: "d1", score_rrf: 0.5 }] };
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    expect((await screen.findAllByText("#2 de 2 em relevância")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("NR-15").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ruído").length).toBeGreaterThan(0);
    expect(screen.queryByText("NR-99")).not.toBeInTheDocument();
  });

  it("com consulta mas sem termos em comum, explica que nada apareceu", async () => {
    sessao = { estrutura: { ...estrutura, normas: ["Súmula 999"], agente_nocivo: [] }, resultados: null };
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    expect(await screen.findByText(/Nenhum termo do seu contexto/)).toBeInTheDocument();
  });

  it("documento magro: textos padrão e sem seções opcionais", async () => {
    getDocumentMock.mockResolvedValue(
      documento({ ementa: "", relatorio: "", fundamentacao: "", acordao: "", votos: "", referencia_legislativa: [], link_original: null, relator: "", tribunal: "" }),
    );
    render(<DecisionDetailPage decisionId="d1" />);
    expect(await screen.findByText("Ementa não disponível para este documento.")).toBeInTheDocument();
    expect(screen.getByText("Rel. Não informado")).toBeInTheDocument();
    expect(screen.getByText("Origem: Não informada")).toBeInTheDocument();
    expect(screen.queryByText("Relatório")).not.toBeInTheDocument();
    expect(screen.queryByText("Votos")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Copiar ementa/ })).not.toBeInTheDocument();
  });

  it("ações: salvar, compartilhar, copiar documento, copiar ementa, copiar processo e refinar", async () => {
    sessao = { estrutura, resultados: [{ id: "d1", score_rrf: 1 }] };
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    await screen.findAllByText("Ementa");

    await userEvent.click(screen.getByRole("button", { name: /Salvar/ }));
    expect(toggle).toHaveBeenCalledWith(expect.objectContaining({ id: "d1" }));

    await userEvent.click(screen.getByRole("button", { name: /Compartilhar/ }));
    expect(copiarMock).toHaveBeenLastCalledWith(window.location.href);
    expect(await screen.findByText("Link copiado!")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Copiar documento/ }));
    const completo = copiarMock.mock.calls.at(-1)[0] as string;
    for (const parte of ["EMENTA", "RELATÓRIO", "FUNDAMENTAÇÃO", "DISPOSITIVO", "INTEIRO TEOR", "VOTOS", "DISPOSITIVOS LEGAIS CITADOS", "ENTIDADES CORRESPONDENTES", "Relevância: #1 de 1", "Fonte: https://exemplo.invalid/doc"]) {
      expect(completo).toContain(parte);
    }

    await userEvent.click(screen.getByRole("button", { name: /Copiar ementa com citação/ }));
    expect(copiarMock.mock.calls.at(-1)[0]).toContain("ADICIONAL DE INSALUBRIDADE");

    await userEvent.click(screen.getByTitle("Copiar número do processo"));
    expect(copiarMock).toHaveBeenLastCalledWith("0001234-56.2024.5.04.0001");

    await userEvent.click(screen.getByRole("button", { name: /Refinar consulta/ }));
    expect(push).toHaveBeenCalledWith("/revisao");
  });

  it("documento já salvo mostra 'Salvo'", async () => {
    salvo = true;
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    expect(await screen.findByRole("button", { name: /^Salvo$/ })).toBeInTheDocument();
  });

  it("seções abrem e fecham, e texto longo pode ser lido inteiro", async () => {
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    await screen.findAllByText("Ementa");
    expect(screen.queryByText("Relatório do caso.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Relatório/ }));
    expect(screen.getByText("Relatório do caso.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Relatório/ }));
    expect(screen.queryByText("Relatório do caso.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Inteiro teor/ }));
    const ler = screen.getByRole("button", { name: /Ler o texto todo/ });
    await userEvent.click(ler);
    expect(screen.getByRole("button", { name: "Mostrar menos" })).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(screen.getByRole("button", { name: /Votos/ }));
    expect(screen.getByText("Voto vencido.")).toBeInTheDocument();
  });

  it("voltar e breadcrumbs levam aos resultados", async () => {
    getDocumentMock.mockResolvedValue(documento());
    render(<DecisionDetailPage decisionId="d1" />);
    await screen.findAllByText("Ementa");
    for (const nome of [/Voltar/, /Jurisprudências/]) {
      const botoes = screen.queryAllByRole("button", { name: nome });
      if (botoes.length) await userEvent.click(botoes[0]);
    }
    expect(push).toHaveBeenCalledWith("/resultados");
  });

  it("404 mostra 'Documento não encontrado' e o botão volta aos resultados", async () => {
    getDocumentMock.mockRejectedValue(new ApiError("Not Found", 404));
    render(<DecisionDetailPage decisionId="x" />);
    expect(await screen.findByRole("heading", { name: "Documento não encontrado" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Voltar aos resultados/ }));
    expect(push).toHaveBeenCalledWith("/resultados");
  });

  it("erro da API mostra a mensagem dela; erro desconhecido, a genérica", async () => {
    getDocumentMock.mockRejectedValueOnce(new ApiError("Serviço indisponível.", 503));
    const { unmount } = render(<DecisionDetailPage decisionId="x" />);
    expect(await screen.findByText("Serviço indisponível.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Não foi possível carregar a decisão" })).toBeInTheDocument();
    unmount();

    getDocumentMock.mockRejectedValueOnce(new Error("rede"));
    render(<DecisionDetailPage decisionId="y" />);
    expect(await screen.findByText("Não foi possível carregar esta decisão agora.")).toBeInTheDocument();
  });

  it("resposta que chega depois de sair da página é ignorada", async () => {
    let resolver: (d: DocumentoDetalhe) => void = () => {};
    let rejeitar: (e: unknown) => void = () => {};
    getDocumentMock.mockReturnValueOnce(new Promise((r) => (resolver = r)));
    getDocumentMock.mockReturnValueOnce(new Promise((_, r) => (rejeitar = r)));
    const a = render(<DecisionDetailPage decisionId="a" />);
    a.unmount();
    const b = render(<DecisionDetailPage decisionId="b" />);
    b.unmount();
    await act(async () => {
      resolver(documento());
      rejeitar(new Error("tarde"));
    });
    expect(screen.queryByText("Carregando decisão…")).not.toBeInTheDocument();
  });
});
