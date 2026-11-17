"use client";

import { useEffect, useState } from "react";
import { gerarResposta, type EstruturaArgumentativa, type RespostaIA } from "@/lib/api";

export const FEEDBACK_KEY = "jurisight:feedback-resposta";
// Voltar da decisão para a lista não gera (nem cobra) a resposta de novo.
const cache = new Map<string, RespostaIA>();

/** aguardando: a triagem ainda avalia (a resposta só é pedida quando ela termina ou é parada). */
export type EstadoResposta =
  | { status: "aguardando" }
  | { status: "carregando" }
  | { status: "erro"; mensagem: string }
  | { status: "ok"; resposta: RespostaIA };

export function lerVotos(): Record<string, "util" | "nao_util"> {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_KEY) ?? "{}");
  } catch {
    return {};
  }
}

/** Pede a resposta (POST /resposta) para as decisões relacionadas, na ordem dos cards (#1 = ids[0]).
 *  `ids` null = ainda não pedir (a triagem está avaliando); lista vazia = nada a responder. */
export function useRespostaGerada(estrutura: EstruturaArgumentativa | null, idsPedidos: string[] | null) {
  const aguardando = idsPedidos === null;
  const ids = estrutura && idsPedidos ? idsPedidos : [];
  const chave = `${ids.join(",")}|${JSON.stringify(estrutura)}`;
  const [recebida, setRecebida] = useState<{ chave: string; erro?: string } | null>(null);

  useEffect(() => {
    if (cache.has(chave) || ids.length === 0 || !estrutura) return;
    let vivo = true;
    gerarResposta(estrutura, ids)
      .then((r) => {
        cache.set(chave, r);
        if (vivo) setRecebida({ chave });
      })
      .catch((e: Error) => vivo && setRecebida({ chave, erro: e.message }));
    return () => {
      vivo = false;
    };
    // `chave` já resume estrutura + ids
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  const pronta = cache.get(chave);
  const estado: EstadoResposta = aguardando
    ? { status: "aguardando" }
    : pronta
    ? { status: "ok", resposta: pronta }
    : recebida?.chave === chave && recebida.erro !== undefined
      ? { status: "erro", mensagem: recebida.erro }
      : { status: "carregando" };
  return { chave, vazia: !aguardando && ids.length === 0, estado };
}
