"use client";

import { createContext, useCallback, useContext, useEffect } from "react";
import { atualizarPerfil } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type Role = "Advogado" | "Assistente Jurídica";

export interface Profile {
  name: string;
  email: string;
  phone: string;
  oab: string;
  role: Role;
}

/** Tudo vem da conta logada (GET /auth/me): nome e e-mail, e também telefone, OAB e papel, que
 *  antes ficavam só no navegador e não apareciam em outro computador (issue #15). */
type Extras = Pick<Profile, "phone" | "oab" | "role">;

const PAPEL_PADRAO: Role = "Advogado";
// Onde os extras ficavam antes: no primeiro acesso, sobem para a conta e saem do navegador.
const CHAVE_SEM_DONO = "jurisight:profile";
const chaveAntigaDe = (usuarioId: string) => `jurisight:profile:${usuarioId}`;

/** Nome exibido: o nome da conta ou, se ela não tiver, a parte do e-mail antes do "@". */
export function nomeExibido(nome: string | null | undefined, email: string | null | undefined): string {
  const n = nome?.trim();
  if (n) return n;
  return email?.split("@")[0] ?? "";
}

interface ProfileCtx {
  profile: Profile;
  /** true quando o usuário da sessão já foi carregado — usado para sincronizar formulários
   *  que copiam o perfil para estado local (ex: ProfileTab). */
  hydrated: boolean;
  /** Grava telefone, OAB e papel na conta; nome e e-mail não mudam por aqui. */
  update: (patch: Partial<Extras>) => Promise<void>;
}

const Ctx = createContext<ProfileCtx | null>(null);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const { usuario, atualizarUsuario } = useAuth();

  const profile: Profile = {
    name: nomeExibido(usuario?.nome, usuario?.email),
    email: usuario?.email ?? "",
    phone: usuario?.telefone ?? "",
    oab: usuario?.oab ?? "",
    role: (usuario?.papel as Role | null | undefined) ?? PAPEL_PADRAO,
  };

  const update = useCallback(
    async (patch: Partial<Extras>) => {
      if (!usuario) return;
      const novo = {
        telefone: patch.phone ?? usuario.telefone ?? "",
        oab: patch.oab ?? usuario.oab ?? "",
        papel: patch.role ?? usuario.papel ?? PAPEL_PADRAO,
      };
      atualizarUsuario(await atualizarPerfil(novo));
    },
    [usuario, atualizarUsuario]
  );

  // Migração única: o que estava salvo no navegador sobe para a conta, se a conta ainda não
  // tiver nada, e a cópia local é apagada.
  const usuarioId = usuario?.id;
  const contaVazia = !usuario?.telefone && !usuario?.oab && !usuario?.papel;
  useEffect(() => {
    if (!usuarioId) return;
    let antigo: Partial<Extras> | null = null;
    try {
      localStorage.removeItem(CHAVE_SEM_DONO);
      const raw = localStorage.getItem(chaveAntigaDe(usuarioId));
      if (raw) antigo = JSON.parse(raw);
      localStorage.removeItem(chaveAntigaDe(usuarioId));
    } catch {
      return; // storage indisponível: não há o que migrar
    }
    if (antigo && contaVazia && (antigo.phone || antigo.oab || antigo.role)) {
      update(antigo).catch(() => {
        /* fica para a próxima vez que a pessoa salvar o perfil */
      });
    }
    // só no primeiro carregamento de cada conta
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuarioId]);

  return <Ctx.Provider value={{ profile, hydrated: !!usuario, update }}>{children}</Ctx.Provider>;
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
