import { useEffect } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, RequireAuth, RequireGuest, useAuth } from "@/lib/auth";
import { ApiError, getUsuarioAtual, loginUsuario, logoutUsuario, type UsuarioPublico } from "@/lib/api";

const replace = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: jest.fn() }) }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  getUsuarioAtual: jest.fn(),
  loginUsuario: jest.fn(),
  logoutUsuario: jest.fn(),
}));

const me = getUsuarioAtual as jest.Mock;
const loginApi = loginUsuario as jest.Mock;
const logoutApi = logoutUsuario as jest.Mock;
const ana: UsuarioPublico = { id: "u1", email: "ana@exemplo.invalid", nome: "Ana", is_active: true, criado_em: "2026-11-01T00:00:00Z" };
const MARCA = "jurisight:sessao";

type Ctx = ReturnType<typeof useAuth>;
const atual: { ctx: Ctx | null } = { ctx: null };
const guardar = (c: Ctx) => {
  atual.ctx = c;
};
function Espia() {
  const ctx = useAuth();
  useEffect(() => guardar(ctx));
  return <p>{ctx.hydrated ? (ctx.isAuthenticated ? `logado:${ctx.usuario?.email}` : "anônimo") : "carregando"}</p>;
}
const montar = (filhos: React.ReactNode = <Espia />) => render(<AuthProvider>{filhos}</AuthProvider>);

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
});

describe("AuthProvider", () => {
  it("sem marca de sessão não chama /auth/me e fica anônimo", async () => {
    montar();
    expect(await screen.findByText("anônimo")).toBeInTheDocument();
    expect(me).not.toHaveBeenCalled();
  });

  it("com marca de sessão confere /auth/me e restaura o usuário", async () => {
    localStorage.setItem(MARCA, "1");
    me.mockResolvedValue(ana);
    montar();
    expect(await screen.findByText("logado:ana@exemplo.invalid")).toBeInTheDocument();
  });

  it("401 no /auth/me apaga a marca; outro erro mantém", async () => {
    localStorage.setItem(MARCA, "1");
    me.mockRejectedValueOnce(new ApiError("expirada", 401));
    const { unmount } = montar();
    expect(await screen.findByText("anônimo")).toBeInTheDocument();
    expect(localStorage.getItem(MARCA)).toBeNull();
    unmount();

    localStorage.setItem(MARCA, "1");
    me.mockRejectedValueOnce(new Error("rede"));
    montar();
    expect(await screen.findByText("anônimo")).toBeInTheDocument();
    expect(localStorage.getItem(MARCA)).toBe("1");
  });

  it("login marca a sessão e guarda o usuário; logout limpa mesmo se a API falhar", async () => {
    loginApi.mockResolvedValue(ana);
    montar();
    await screen.findByText("anônimo");
    await act(() => atual.ctx!.login("ana@exemplo.invalid", "segredo"));
    expect(loginApi).toHaveBeenCalledWith({ email: "ana@exemplo.invalid", password: "segredo" });
    expect(localStorage.getItem(MARCA)).toBe("1");
    expect(screen.getByText("logado:ana@exemplo.invalid")).toBeInTheDocument();

    logoutApi.mockRejectedValue(new Error("já expirou"));
    await act(async () => {
      await atual.ctx!.logout().catch(() => {});
    });
    expect(localStorage.getItem(MARCA)).toBeNull();
    expect(screen.getByText("anônimo")).toBeInTheDocument();
  });

  it("atualizarUsuario troca o usuário da sessão", async () => {
    montar();
    await screen.findByText("anônimo");
    act(() => atual.ctx!.atualizarUsuario({ ...ana, email: "novo@exemplo.invalid" }));
    expect(screen.getByText("logado:novo@exemplo.invalid")).toBeInTheDocument();
  });

  it("sem localStorage, confere sempre e não quebra ao marcar", async () => {
    const getItem = jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    const setItem = jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    me.mockResolvedValue(null);
    loginApi.mockResolvedValue(ana);
    montar();
    await screen.findByText("anônimo");
    expect(me).toHaveBeenCalled();
    await act(() => atual.ctx!.login("a", "b"));
    expect(screen.getByText("logado:ana@exemplo.invalid")).toBeInTheDocument();
    getItem.mockRestore();
    setItem.mockRestore();
  });

  it("useAuth fora do provider avisa", () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Espia />)).toThrow("useAuth precisa de <AuthProvider>.");
  });
});

describe("RequireAuth / RequireGuest", () => {
  it("RequireAuth manda o anônimo para /login e não mostra o conteúdo", async () => {
    montar(<RequireAuth><p>área logada</p></RequireAuth>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("área logada")).not.toBeInTheDocument();
  });

  it("RequireAuth mostra o conteúdo para quem está logado", async () => {
    localStorage.setItem(MARCA, "1");
    me.mockResolvedValue(ana);
    montar(<RequireAuth><p>área logada</p></RequireAuth>);
    expect(await screen.findByText("área logada")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("RequireGuest manda quem está logado para / e mostra o conteúdo ao anônimo", async () => {
    localStorage.setItem(MARCA, "1");
    me.mockResolvedValue(ana);
    const { unmount } = montar(<RequireGuest><p>tela de login</p></RequireGuest>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("tela de login")).not.toBeInTheDocument();
    unmount();

    localStorage.clear();
    montar(<RequireGuest><p>tela de login</p></RequireGuest>);
    expect(await screen.findByText("tela de login")).toBeInTheDocument();
  });
});
