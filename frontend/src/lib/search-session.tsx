"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { emptyEstrutura, type EstruturaArgumentativa, type ExpressaoSugerida, type ResultCard, type SugestaoDispositivo } from "@/lib/api";
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
  /** Códigos de dispositivos sugeridos pela IA no /enrich (para o selo na Revisão). */
  dispositivosIa: string[];
  /** true quando os resultados vêm de uma busca que acabou de rodar (a triagem por IA começa
   *  sozinha); false ao reabrir uma versão (a triagem só lê o cache, sem gastar). */
  buscaNova: boolean;
  /** Decisões marcadas "É relevante" na versão exibida. */
  relevantesUsuario: string[];
  /** Decisões que foram à resposta gerada da versão exibida, na ordem #1..#k. */
  respostaIds: string[];
  /** Expressões sugeridas pela IA no /enrich: só viram filtro se o advogado clicar. */
  expressoesSugeridas: ExpressaoSugerida[];
  /** Dispositivos que a IA relaciona ao tema: também só viram filtro com o clique. */
  dispositivosSugeridos: SugestaoDispositivo[];
}

interface EnrichResultInput {
  estrutura: EstruturaArgumentativa;
  hasFile: boolean;
  fileName: string | null;
  pdfExtraido: boolean | null;
  aviso: string | null;
  dispositivosIa?: string[];
  expressoesSugeridas?: ExpressaoSugerida[];
  dispositivosSugeridos?: SugestaoDispositivo[];
}

interface SearchSessionCtx extends SearchSessionState {
  setEnrichResult: (data: EnrichResultInput) => void;
  setEstrutura: (estrutura: EstruturaArgumentativa) => void;
  /** Troca a sessão pra uma versão específica da conversa ativa — usado tanto ao reabrir
   *  uma conversa pela sidebar (a versão mais recente) quanto ao trocar de versão pelo
   *  dropdown V1/V2/... na página de Resultados (sem chamar a API de novo — a versão já
   *  veio inteira do backend). */
  loadVersion: (version: ConversationVersion, opcoes?: { buscaNova?: boolean }) => void;
  /** Atualiza os votos da versão exibida (depois de gravar na conversa). */
  setRelevantesUsuario: (ids: string[]) => void;
  /** Atualiza as decisões da resposta da versão exibida (depois de gravar na conversa). */
  setRespostaIds: (ids: string[]) => void;
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
  buscaNova: false,
  relevantesUsuario: [],
  respostaIds: [],
  dispositivosIa: [],
  expressoesSugeridas: [],
  dispositivosSugeridos: [],
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
      dispositivosIa: data.dispositivosIa ?? [],
      expressoesSugeridas: data.expressoesSugeridas ?? [],
      dispositivosSugeridos: data.dispositivosSugeridos ?? [],
      versionNumero: null, // ainda não existe versão — só depois do 1º /query bem-sucedido
    }));
  }, []);

  const setEstrutura = useCallback((estrutura: EstruturaArgumentativa) => {
    setState((prev) => ({ ...prev, estrutura }));
  }, []);

  const loadVersion = useCallback((version: ConversationVersion, opcoes?: { buscaNova?: boolean }) => {
    setState({
      // versões salvas antes do filtro restrito não têm esses campos
      estrutura: { ...emptyEstrutura(), ...version.estrutura },
      hasFile: version.hasFile,
      fileName: version.fileName,
      pdfExtraido: version.pdfExtraido,
      aviso: version.aviso,
      resultados: version.resultados,
      versionNumero: version.numero,
      buscaNova: opcoes?.buscaNova ?? false,
      relevantesUsuario: version.relevantesUsuario ?? [],
      respostaIds: version.respostaIds ?? [],
      dispositivosIa: [],
      expressoesSugeridas: [],
      dispositivosSugeridos: [],
    });
  }, []);

  const setRelevantesUsuario = useCallback((ids: string[]) => {
    setState((prev) => ({ ...prev, relevantesUsuario: ids }));
  }, []);

  const setRespostaIds = useCallback((ids: string[]) => {
    setState((prev) => ({ ...prev, respostaIds: ids }));
  }, []);

  const reset = useCallback(() => setState(initialState), []);

  return (
    <Ctx.Provider value={{ ...state, setEnrichResult, setEstrutura, loadVersion, setRelevantesUsuario, setRespostaIds, reset }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSearchSession() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearchSession precisa de <SearchSessionProvider>.");
  return ctx;
}
