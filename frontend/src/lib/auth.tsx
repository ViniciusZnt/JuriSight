"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

/** Sessão mockada — não há backend de autenticação (fora do escopo do RFC). Login e Cadastro
 *  apenas gravam uma flag local; serve para exercitar proteção de rotas e logout. */
const STORAGE_KEY = "jurisight:auth";

interface AuthCtx {
  isAuthenticated: boolean;
  /** true assim que o localStorage foi lido — evita decidir redirect com um valor "adivinhado". */
  hydrated: boolean;
  login: () => void;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      setIsAuthenticated(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* storage indisponível — segue deslogado */
    }
    setHydrated(true);
  }, []);

  const login = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignora */
    }
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignora */
    }
    setIsAuthenticated(false);
  }, []);

  return <Ctx.Provider value={{ isAuthenticated, hydrated, login, logout }}>{children}</Ctx.Provider>;
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
