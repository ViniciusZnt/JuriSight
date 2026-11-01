"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

export type Role = "Advogado" | "Assistente Jurídica";

export interface Profile {
  name: string;
  email: string;
  phone: string;
  oab: string;
  role: Role;
}

/** Só o que não existe no backend fica no navegador (telefone, OAB, papel), separado por usuário.
 *  Nome e e-mail vêm sempre da conta logada (GET /auth/me). */
type Extras = Pick<Profile, "phone" | "oab" | "role">;

const EXTRAS_PADRAO: Extras = { phone: "", oab: "", role: "Advogado" };
const CHAVE_ANTIGA = "jurisight:profile"; // perfil fixo de antes, sem dono: é apagado
const chaveDe = (usuarioId: string) => `jurisight:profile:${usuarioId}`;

/** Nome exibido: o nome da conta ou, se ela não tiver, a parte do e-mail antes do "@". */
export function nomeExibido(nome: string | null | undefined, email: string | null | undefined): string {
  const n = nome?.trim();
  if (n) return n;
  return email?.split("@")[0] ?? "";
}

interface ProfileCtx {
  profile: Profile;
  /** true assim que os dados extras do usuário foram lidos do localStorage — usado para
   *  sincronizar formulários que copiam o perfil para estado local (ex: ProfileTab). */
  hydrated: boolean;
  /** Atualiza só telefone, OAB e papel; nome e e-mail pertencem à conta. */
  update: (patch: Partial<Extras>) => void;
}

const Ctx = createContext<ProfileCtx | null>(null);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const { usuario } = useAuth();
  const usuarioId = usuario?.id ?? null;
  const [extras, setExtras] = useState<Extras>(EXTRAS_PADRAO);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(false);
    setExtras(EXTRAS_PADRAO);
    if (!usuarioId) return;
    try {
      localStorage.removeItem(CHAVE_ANTIGA);
      const raw = localStorage.getItem(chaveDe(usuarioId));
      if (raw) setExtras({ ...EXTRAS_PADRAO, ...JSON.parse(raw) });
    } catch {
      /* storage indisponível — segue no padrão */
    }
    setHydrated(true);
  }, [usuarioId]);

  const update = useCallback(
    (patch: Partial<Extras>) => {
      setExtras((prev) => {
        const novo = { ...prev, ...patch };
        if (usuarioId) {
          try {
            localStorage.setItem(chaveDe(usuarioId), JSON.stringify(novo));
          } catch {
            /* ignora */
          }
        }
        return novo;
      });
    },
    [usuarioId]
  );

  const profile: Profile = {
    name: nomeExibido(usuario?.nome, usuario?.email),
    email: usuario?.email ?? "",
    ...extras,
  };

  return <Ctx.Provider value={{ profile, hydrated, update }}>{children}</Ctx.Provider>;
}

export function useProfile() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useProfile precisa de <ProfileProvider>.");
  return ctx;
}

/** Iniciais para o avatar (até 2 letras), a partir do nome completo. */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
