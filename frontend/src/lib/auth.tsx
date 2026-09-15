"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { getUsuarioAtual, loginUsuario, logoutUsuario, type UsuarioPublico } from "@/lib/api";

/** Sessão real: cookie httpOnly emitido por POST /auth/login (query/api/auth_routes.py).
 *  Este contexto nunca vê o token — só sabe se GET /auth/me responde com um usuário. */
interface AuthCtx {
  isAuthenticated: boolean;
  usuario: UsuarioPublico | null;
  /** true assim que a checagem de sessão (GET /auth/me) respondeu — evita decidir
   *  redirect com um valor "adivinhado" antes da API responder. */
  hydrated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioPublico | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    getUsuarioAtual()
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setHydrated(true));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const usuarioLogado = await loginUsuario({ email, password });
    setUsuario(usuarioLogado);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutUsuario();
    } finally {
      // Limpa a sessão local mesmo se a chamada ao backend falhar (ex.: já
      // expirado) — não faz sentido travar o usuário numa sessão "zumbi".
      setUsuario(null);
    }
  }, []);

  return (
    <Ctx.Provider value={{ isAuthenticated: usuario !== null, usuario, hydrated, login, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth precisa de <AuthProvider>.");
  return ctx;
}

/** Protege as telas autenticadas: redireciona para /login enquanto não há sessão. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, hydrated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (hydrated && !isAuthenticated) router.replace("/login");
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) return null;
  return <>{children}</>;
}

/** Protege as telas de login/cadastro: quem já está logado é mandado direto para o app. */
export function RequireGuest({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, hydrated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (hydrated && isAuthenticated) router.replace("/");
  }, [hydrated, isAuthenticated, router]);

  if (hydrated && isAuthenticated) return null;
  return <>{children}</>;
}
