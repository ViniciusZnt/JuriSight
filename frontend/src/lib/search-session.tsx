"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { EstruturaArgumentativa, ResultCard } from "@/lib/api";
import type { ConversationSnapshot } from "@/lib/conversations";

interface SearchSessionState {
  /** EstruturaArgumentativa retornada por /enrich (ou editada na Revisão). null = nenhuma
   *  consulta em andamento (usuário ainda não passou pela Home nesta sessão). */
  estrutura: EstruturaArgumentativa | null;
  hasFile: boolean;
  fileName: string | null;
  pdfExtraido: boolean | null;
  aviso: string | null;
  /** Resultado do último POST /query. null = nenhuma busca feita ainda. */
  resultados: ResultCard[] | null;
}

interface EnrichResultInput {
  estrutura: EstruturaArgumentativa;
  hasFile: boolean;
  fileName: string | null;
  pdfExtraido: boolean | null;
  aviso: string | null;
}

interface SearchSessionCtx extends SearchSessionState {
  setEnrichResult: (data: EnrichResultInput) => void;
  setEstrutura: (estrutura: EstruturaArgumentativa) => void;
  setResultados: (resultados: ResultCard[]) => void;
  /** Restaura a sessão a partir do snapshot salvo numa conversa (clique no histórico da
   *  sidebar) — ao contrário de setEnrichResult, também repõe os resultados, se houver. */
  loadSnapshot: (snapshot: ConversationSnapshot) => void;
  reset: () => void;
}

const initialState: SearchSessionState = {
  estrutura: null,
  hasFile: false,
  fileName: null,
  pdfExtraido: null,
  aviso: null,
  resultados: null,
};

const Ctx = createContext<SearchSessionCtx | null>(null);

/** Estado do fluxo de consulta (Home -> Revisão -> Resultados -> Decisão) — a ponte entre as
 *  páginas para a EstruturaArgumentativa e os resultados vindos da API. Vive só em memória
 *  (como qualquer wizard client-side): um reload duro reinicia o fluxo pela Home. */
export function SearchSessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SearchSessionState>(initialState);

  const setEnrichResult = useCallback((data: EnrichResultInput) => {
    setState((prev) => ({
      ...prev,
      estrutura: data.estrutura,
      hasFile: data.hasFile,
      fileName: data.fileName,
      pdfExtraido: data.pdfExtraido,
      aviso: data.aviso,
      resultados: null, // nova consulta invalida os resultados anteriores
    }));
  }, []);

  const setEstrutura = useCallback((estrutura: EstruturaArgumentativa) => {
    setState((prev) => ({ ...prev, estrutura }));
  }, []);

  const setResultados = useCallback((resultados: ResultCard[]) => {
    setState((prev) => ({ ...prev, resultados }));
  }, []);

  const loadSnapshot = useCallback((snapshot: ConversationSnapshot) => {
    setState({
      estrutura: snapshot.estrutura,
      hasFile: snapshot.hasFile,
      fileName: snapshot.fileName,
      pdfExtraido: snapshot.pdfExtraido,
      aviso: snapshot.aviso,
      resultados: snapshot.resultados,
    });
  }, []);

  const reset = useCallback(() => setState(initialState), []);

  return (
    <Ctx.Provider value={{ ...state, setEnrichResult, setEstrutura, setResultados, loadSnapshot, reset }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSearchSession() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearchSession precisa de <SearchSessionProvider>.");
  return ctx;
}
