import { act, renderHook } from "@testing-library/react";
import { ProfileProvider, useProfile } from "@/lib/profile";
import { atualizarPerfil, type UsuarioPublico } from "@/lib/api";

const base: UsuarioPublico = { id: "u1", email: "ana@exemplo.com", nome: "Ana", is_active: true, criado_em: "2026-01-01" };
let mockUsuario: UsuarioPublico | null = base;
const mockAtualizarUsuario = jest.fn((u: UsuarioPublico) => {
  mockUsuario = u;
});
jest.mock("@/lib/auth", () => ({ useAuth: () => ({ usuario: mockUsuario, atualizarUsuario: mockAtualizarUsuario }) }));
jest.mock("@/lib/api", () => ({ atualizarPerfil: jest.fn() }));
const api = atualizarPerfil as jest.Mock;

beforeEach(() => {
  mockUsuario = base;
  mockAtualizarUsuario.mockClear();
  api.mockReset();
  window.localStorage.clear();
});

describe("ProfileProvider (issue #15)", () => {
  it("telefone, OAB e papel vêm da conta, não do navegador", () => {
    mockUsuario = { ...base, telefone: "(48) 1", oab: "1/SC", papel: "Assistente Jurídica" };
    const { result } = renderHook(() => useProfile(), { wrapper: ProfileProvider });
    expect(result.current.profile).toMatchObject({ name: "Ana", phone: "(48) 1", oab: "1/SC", role: "Assistente Jurídica" });
  });

  it("salvar grava na conta e atualiza a sessão", async () => {
    api.mockResolvedValue({ ...base, telefone: "(48) 2", oab: null, papel: "Advogado" });
    const { result } = renderHook(() => useProfile(), { wrapper: ProfileProvider });
    await act(() => result.current.update({ phone: "(48) 2" }));
    expect(api).toHaveBeenCalledWith({ telefone: "(48) 2", oab: "", papel: "Advogado" });
    expect(mockAtualizarUsuario).toHaveBeenCalledWith(expect.objectContaining({ telefone: "(48) 2" }));
  });
});
