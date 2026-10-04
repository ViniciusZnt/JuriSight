"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { EstruturaArgumentativa, ResultCard } from "@/lib/api";
import type { ConversationVersion } from "@/lib/conversations";

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
  /** Número da versão (V1, V2, ...) atualmente exibida — null antes da primeira busca
   *  completar (ainda não existe versão pra essa conversa). Ver @/lib/conversations. */
  versionNumero: number | null;
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
  /** Troca a sessão pra uma versão específica da conversa ativa — usado tanto ao reabrir
   *  uma conversa pela sidebar (a versão mais recente) quanto ao trocar de versão pelo
   *  dropdown V1/V2/... na página de Resultados (sem chamar a API de novo — a versão já
   *  veio inteira do backend). */
  loadVersion: (version: ConversationVersion) => void;
  reset: () => void;
}

const initialState: SearchSessionState = {
  estrutura: null,
  hasFile: false,
  fileName: null,
  pdfExtraido: null,
  aviso: null,
  resultados: null,
  versionNumero: null,
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
      versionNumero: null, // ainda não existe versão — só depois do 1º /query bem-sucedido
    }));
  }, []);

  const setEstrutura = useCallback((estrutura: EstruturaArgumentativa) => {
    setState((prev) => ({ ...prev, estrutura }));
  }, []);

  const loadVersion = useCallback((version: ConversationVersion) => {
    setState({
      estrutura: version.estrutura,
      hasFile: version.hasFile,
      fileName: version.fileName,
      pdfExtraido: version.pdfExtraido,
      aviso: version.aviso,
      resultados: version.resultados,
      versionNumero: version.numero,
    });
  }, []);

  const reset = useCallback(() => setState(initialState), []);

  return (
    <Ctx.Provider value={{ ...state, setEnrichResult, setEstrutura, loadVersion, reset }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSearchSession() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearchSession precisa de <SearchSessionProvider>.");
  return ctx;
}
