"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getUso, type UsoAcao } from "@/lib/api";

interface UsoDiarioCtx {
  /** null = ainda não chegou ou GET /uso falhou (o indicador some). */
  acoes: UsoAcao[] | null;
  /** Busca o uso de novo: chamado depois de cada chamada paga (enrich, query, lote da triagem, resposta). */
  atualizar: () => void;
}

const Ctx = createContext<UsoDiarioCtx | null>(null);
const FORA_DO_PROVIDER: UsoDiarioCtx = { acoes: null, atualizar: () => {} };

/** Uso de hoje da conta, para o indicador da sidebar. Nunca bloqueia nada: falhou, some. */
export function UsoDiarioProvider({ children }: { children: React.ReactNode }) {
  const [acoes, setAcoes] = useState<UsoAcao[] | null>(null);

  const atualizar = useCallback(() => {
    getUso()
      .then((r) => setAcoes(r.acoes))
      .catch(() => setAcoes(null));
  }, []);

  useEffect(() => {
    atualizar();
  }, [atualizar]);

  return <Ctx.Provider value={{ acoes, atualizar }}>{children}</Ctx.Provider>;
}

export function useUsoDiario(): UsoDiarioCtx {
  return useContext(Ctx) ?? FORA_DO_PROVIDER;
}
