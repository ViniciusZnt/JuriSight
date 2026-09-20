"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Role = "Advogado" | "Assistente Jurídica";

export interface Profile {
  name: string;
  email: string;
  phone: string;
  oab: string;
  role: Role;
}

const STORAGE_KEY = "jurisight:profile";

const DEFAULT_PROFILE: Profile = {
  name: "Marcos Almeida",
  email: "marcos.almeida@escritorio.com.br",
  phone: "",
  oab: "",
  role: "Advogado",
};

interface ProfileCtx {
  profile: Profile;
  /** true assim que o localStorage foi lido — usado para sincronizar formulários que copiam
   *  o perfil para estado local (ex: ProfileTab) só depois que o valor real chegou. */
  hydrated: boolean;
  update: (patch: Partial<Profile>) => void;
}

const Ctx = createContext<ProfileCtx | null>(null);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setProfile({ ...DEFAULT_PROFILE, ...JSON.parse(raw) });
    } catch {
      /* storage indisponível — segue no padrão */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
    } catch {
      /* ignora */
    }
  }, [profile, hydrated]);

  const update = useCallback((patch: Partial<Profile>) => {
    setProfile((prev) => ({ ...prev, ...patch }));
  }, []);

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
