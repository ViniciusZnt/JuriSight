"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { EstruturaArgumentativa, ResultCard } from "@/lib/api";

/** Estado de sessão da consulta em andamento (Home → Revisão → Resultados).
 *
 *  Sem persistência em localStorage de propósito: a EstruturaArgumentativa é
 *  "memória de sessão" no próprio RFC (§6.1 LGPD) — perder o estado num reload
 *  é o comportamento correto, não um bug. */
interface ConsultaCtx {
  fileName: string | null;
  estrutura: EstruturaArgumentativa | null;
  resultados: ResultCard[] | null;
  setEnriched: (fileName: string | null, estrutura: EstruturaArgumentativa) => void;
  setResultados: (resultados: ResultCard[]) => void;
  reset: () => void;
}

const Ctx = createContext<ConsultaCtx | null>(null);

export function ConsultaProvider({ children }: { children: React.ReactNode }) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [estrutura, setEstrutura] = useState<EstruturaArgumentativa | null>(null);
  const [resultados, setResultadosState] = useState<ResultCard[] | null>(null);

  const setEnriched = useCallback((fn: string | null, e: EstruturaArgumentativa) => {
    setFileName(fn);
    setEstrutura(e);
    setResultadosState(null); // uma nova consulta invalida os resultados da anterior
  }, []);

  const setResultados = useCallback((r: ResultCard[]) => setResultadosState(r), []);

  const reset = useCallback(() => {
    setFileName(null);
    setEstrutura(null);
    setResultadosState(null);
  }, []);

  return (
    <Ctx.Provider value={{ fileName, estrutura, resultados, setEnriched, setResultados, reset }}>
      {children}
    </Ctx.Provider>
  );
}

export function useConsulta() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConsulta precisa de <ConsultaProvider>.");
  return ctx;
}
