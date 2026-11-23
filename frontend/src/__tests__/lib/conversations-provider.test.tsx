import { act, render, renderHook, waitFor } from "@testing-library/react";
import { ConversationsProvider, useConversations } from "@/lib/conversations";
import {
  adicionarVersaoConversa, apagarConversa, atualizarVersao, criarConversa, emptyEstrutura, listarConversas, renomearConversa,
  type ConversaApi, type VersaoApi,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  listarConversas: jest.fn(),
  criarConversa: jest.fn(),
  renomearConversa: jest.fn(),
  apagarConversa: jest.fn(),
  adicionarVersaoConversa: jest.fn(),
  atualizarVersao: jest.fn(),
}));

const listar = listarConversas as jest.Mock;
const criar = criarConversa as jest.Mock;
const renomear = renomearConversa as jest.Mock;
const apagar = apagarConversa as jest.Mock;
const addVersao = adicionarVersaoConversa as jest.Mock;
const atualizarV = atualizarVersao as jest.Mock;

const versaoApi = (numero: number, extra: Partial<VersaoApi> = {}): VersaoApi => ({
  numero, estrutura: emptyEstrutura(), has_file: false, file_name: null, pdf_extraido: null, aviso: null,
  resultados: null, criado_em: "2026-11-20T10:00:00Z", ...extra,
});
const conversa = (id: string, titulo = id, versoes: VersaoApi[] = []): ConversaApi => ({
  id, titulo, criado_em: "2026-11-20T10:00:00Z", atualizado_em: "2026-11-20T10:00:00Z", versoes,
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ConversationsProvider>{children}</ConversationsProvider>;
const montar = async () => {
  const h = renderHook(useConversations, { wrapper });
  await waitFor(() => expect(h.result.current.loading).toBe(false));
  return h;
};

beforeEach(() => {
  jest.clearAllMocks();
  listar.mockResolvedValue([conversa("c1", "Antiga", [versaoApi(1, { relevantes_usuario: ["d1"] })])]);
});

describe("ConversationsProvider", () => {
  it("carrega a lista da API ao montar, convertendo as versões", async () => {
    const { result } = await montar();
    expect(result.current.conversations).toHaveLength(1);
    const [c] = result.current.conversations;
    expect(c).toMatchObject({ id: "c1", title: "Antiga" });
    expect(c.versions[0]).toMatchObject({ numero: 1, relevantesUsuario: ["d1"], respostaIds: [], createdAt: Date.parse("2026-11-20T10:00:00Z") });
  });

  it("falha ao carregar não derruba: lista vazia e loading termina", async () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    listar.mockRejectedValue(new Error("rede"));
    const { result } = await montar();
    expect(result.current.conversations).toEqual([]);
  });

  it("resposta que chega depois de desmontar é ignorada", async () => {
    let resolver: (v: ConversaApi[]) => void = () => {};
    listar.mockReturnValue(new Promise((r) => (resolver = r)));
    const { unmount } = renderHook(useConversations, { wrapper });
    unmount();
    await act(async () => resolver([conversa("tarde")]));
  });

  it("create põe a conversa no topo e ativa; título vazio vira 'Nova pesquisa'", async () => {
    criar.mockResolvedValue(conversa("c2", "Nova pesquisa"));
    const { result } = await montar();
    let id = "";
    await act(async () => {
      id = await result.current.create("   ");
    });
    expect(criar).toHaveBeenCalledWith("Nova pesquisa");
    expect(id).toBe("c2");
    expect(result.current.activeId).toBe("c2");
    expect(result.current.conversations.map((c) => c.id)).toEqual(["c2", "c1"]);
  });

  it("rename troca só a conversa certa (título vazio vira 'Nova pesquisa')", async () => {
    renomear.mockResolvedValue(conversa("c1", "Renomeada"));
    const { result } = await montar();
    await act(() => result.current.rename("c1", "  Renomeada  "));
    expect(renomear).toHaveBeenCalledWith("c1", "Renomeada");
    await act(() => result.current.rename("c1", ""));
    expect(renomear).toHaveBeenLastCalledWith("c1", "Nova pesquisa");
    expect(result.current.conversations[0].title).toBe("Renomeada");
  });

  it("remove tira da lista e desativa se era a ativa", async () => {
    apagar.mockResolvedValue(undefined);
    listar.mockResolvedValue([conversa("c1"), conversa("c2")]);
    const { result } = await montar();
    act(() => result.current.setActive("c1"));
    await act(() => result.current.remove("c2"));
    expect(result.current.activeId).toBe("c1");
    await act(() => result.current.remove("c1"));
    expect(result.current.activeId).toBeNull();
    expect(result.current.conversations).toEqual([]);
  });

  it("addVersion manda o snapshot no formato da API e devolve a última versão", async () => {
    addVersao.mockResolvedValue(conversa("c1", "Antiga", [versaoApi(1), versaoApi(2, { has_file: true, file_name: "a.pdf" })]));
    const { result } = await montar();
    let nova;
    await act(async () => {
      nova = await result.current.addVersion("c1", {
        estrutura: emptyEstrutura(), hasFile: true, fileName: "a.pdf", pdfExtraido: true, aviso: null, resultados: [],
      });
    });
    expect(addVersao).toHaveBeenCalledWith("c1", {
      estrutura: emptyEstrutura(), has_file: true, file_name: "a.pdf", pdf_extraido: true, aviso: null, resultados: [],
    });
    expect(nova).toMatchObject({ numero: 2, hasFile: true });
    expect(result.current.conversations[0].versions).toHaveLength(2);
  });

  it("setRelevantes e setRespostaIds gravam na versão e atualizam a lista", async () => {
    atualizarV.mockResolvedValue(conversa("c1", "Antiga", [versaoApi(1, { relevantes_usuario: ["x"], resposta_ids: ["y"] })]));
    const { result } = await montar();
    await act(() => result.current.setRelevantes("c1", 1, ["x"]));
    expect(atualizarV).toHaveBeenCalledWith("c1", 1, { relevantes_usuario: ["x"] });
    await act(() => result.current.setRespostaIds("c1", 1, ["y"]));
    expect(atualizarV).toHaveBeenLastCalledWith("c1", 1, { resposta_ids: ["y"] });
    expect(result.current.conversations[0].versions[0]).toMatchObject({ relevantesUsuario: ["x"], respostaIds: ["y"] });
  });

  it("fora do provider avisa", () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    function Sem() {
      useConversations();
      return null;
    }
    expect(() => render(<Sem />)).toThrow("useConversations precisa de <ConversationsProvider>.");
  });
});
