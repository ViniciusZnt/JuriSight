/**
 * Testes do cliente HTTP (lib/api.ts). global.fetch é mockado — os testes validam a
 * montagem das requisições (multipart vs JSON, URL, método, cookie de sessão) e o
 * tratamento de erro (ApiError em 4xx/5xx), sem bater num backend real.
 */
import {
  enrich,
  queryJurisprudencia,
  getDocument,
  registrarUsuario,
  loginUsuario,
  logoutUsuario,
  getUsuarioAtual,
  ApiError,
  type EstruturaArgumentativa,
} from "@/lib/api";

function mockFetchOnce(status: number, body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as jest.Mock;
}

const estrutura: EstruturaArgumentativa = {
  pedido_principal: "adicional de insalubridade",
  agente_nocivo: ["benzeno"],
  violacoes: [],
  normas: [],
  empresa_ciente: null,
  setor: null,
  cargo: null,
  tese_central: "tese",
};

afterEach(() => {
  jest.restoreAllMocks();
});

// --------------------------------------------------------------------------- //
// enrich                                                                        //
// --------------------------------------------------------------------------- //

describe("enrich", () => {
  it("envia multipart com pdf e intencao quando os dois existem", async () => {
    mockFetchOnce(200, { estrutura, pdf_extraido: true, aviso: null });
    const pdf = new File(["conteudo"], "caso.pdf", { type: "application/pdf" });

    await enrich({ pdf, intencao: "minha intenção" });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/enrich$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("pdf")).toBe(pdf);
    expect((init.body as FormData).get("intencao")).toBe("minha intenção");
  });

  it("omite o campo pdf quando não há arquivo (FA01)", async () => {
    mockFetchOnce(200, { estrutura, pdf_extraido: null, aviso: null });
    await enrich({ intencao: "só intenção" });

    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect((init.body as FormData).get("pdf")).toBeNull();
  });

  it("retorna o EnrichResponse decodificado", async () => {
    mockFetchOnce(200, { estrutura, pdf_extraido: true, aviso: null });
    const resp = await enrich({ intencao: "x" });
    expect(resp.estrutura).toEqual(estrutura);
    expect(resp.pdf_extraido).toBe(true);
  });

  it("levanta ApiError com o detail do backend em erro HTTP", async () => {
    mockFetchOnce(422, { detail: "Nada para enriquecer." });
    await expect(enrich({})).rejects.toThrow(ApiError);
    await expect(enrich({})).rejects.toThrow("Nada para enriquecer.");
  });
});

// --------------------------------------------------------------------------- //
// queryJurisprudencia                                                          //
// --------------------------------------------------------------------------- //

describe("queryJurisprudencia", () => {
  it("envia JSON com Content-Type correto", async () => {
    mockFetchOnce(200, []);
    await queryJurisprudencia({ estrutura, provimento: "APROVADO", ordenar_por: "data" });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/query$/);
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(init.body);
    expect(body.estrutura).toEqual(estrutura);
    expect(body.provimento).toBe("APROVADO");
    expect(body.ordenar_por).toBe("data");
  });

  it("retorna a lista de ResultCard", async () => {
    const cards = [{ id: "1", tipo_documento: "ACORDAO" }];
    mockFetchOnce(200, cards);
    const resp = await queryJurisprudencia({ estrutura });
    expect(resp).toEqual(cards);
  });

  it("levanta ApiError em erro HTTP sem detail (usa mensagem padrão)", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("não é JSON");
      },
    }) as jest.Mock;
    await expect(queryJurisprudencia({ estrutura })).rejects.toThrow(/Erro 500/);
  });
});

// --------------------------------------------------------------------------- //
// getDocument                                                                   //
// --------------------------------------------------------------------------- //

describe("getDocument", () => {
  it("chama GET /document/{id} com o id codificado na URL", async () => {
    mockFetchOnce(200, { id: "abc-123" });
    await getDocument("abc 123");

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/document\/abc%20123$/);
    expect(init.credentials).toBe("include");
  });

  it("levanta ApiError 404 quando o documento não existe", async () => {
    mockFetchOnce(404, { detail: "Documento não encontrado." });
    await expect(getDocument("nao-existe")).rejects.toMatchObject({ status: 404 });
  });
});

// --------------------------------------------------------------------------- //
// credenciais de sessão (cookie httpOnly)                                      //
// --------------------------------------------------------------------------- //

describe("credentials", () => {
  it("toda chamada inclui credentials: 'include' (cookie de sessão)", async () => {
    mockFetchOnce(200, { estrutura, pdf_extraido: null, aviso: null });
    await enrich({ intencao: "x" });
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(init.credentials).toBe("include");
  });
});

// --------------------------------------------------------------------------- //
// autenticação (query/api/auth_routes.py)                                      //
// --------------------------------------------------------------------------- //

describe("registrarUsuario", () => {
  it("envia POST /auth/registro com o header anti-CSRF", async () => {
    mockFetchOnce(200, { id: "1", email: "a@b.com", nome: null, is_active: true, criado_em: "" });
    await registrarUsuario({ email: "a@b.com", password: "segredo123" });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/auth\/registro$/);
    expect(init.method).toBe("POST");
    expect(init.headers["X-Requested-With"]).toBe("XMLHttpRequest");
    expect(init.headers["Content-Type"]).toBe("application/json");
  });
});

describe("loginUsuario", () => {
  it("envia POST /auth/login com o header anti-CSRF", async () => {
    mockFetchOnce(200, { id: "1", email: "a@b.com", nome: null, is_active: true, criado_em: "" });
    await loginUsuario({ email: "a@b.com", password: "segredo123" });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/auth\/login$/);
    expect(init.headers["X-Requested-With"]).toBe("XMLHttpRequest");
  });

  it("levanta ApiError 401 em credenciais inválidas", async () => {
    mockFetchOnce(401, { detail: "Email ou senha inválidos." });
    await expect(loginUsuario({ email: "a@b.com", password: "errada" })).rejects.toMatchObject({ status: 401 });
  });
});

describe("logoutUsuario", () => {
  it("envia POST /auth/logout com o header anti-CSRF", async () => {
    mockFetchOnce(204, undefined);
    await logoutUsuario();

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/auth\/logout$/);
    expect(init.method).toBe("POST");
    expect(init.headers["X-Requested-With"]).toBe("XMLHttpRequest");
  });
});

describe("getUsuarioAtual", () => {
  it("chama GET /auth/me e retorna o usuário da sessão", async () => {
    mockFetchOnce(200, { id: "1", email: "a@b.com", nome: "A", is_active: true, criado_em: "" });
    const user = await getUsuarioAtual();
    expect(user.email).toBe("a@b.com");
  });

  it("levanta ApiError 401 sem sessão válida", async () => {
    mockFetchOnce(401, { detail: "Não autenticado." });
    await expect(getUsuarioAtual()).rejects.toMatchObject({ status: 401 });
  });
});
