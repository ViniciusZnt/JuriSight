"use client";

import { useEffect, useState } from "react";
import { gerarResposta, type EstruturaArgumentativa, type RespostaIA, type ResultCard } from "@/lib/api";

export const FEEDBACK_KEY = "jurisight:feedback-resposta";
// Voltar da decisão para a lista não gera (nem cobra) a resposta de novo.
const cache = new Map<string, RespostaIA>();

export type EstadoResposta = { status: "carregando" } | { status: "erro"; mensagem: string } | { status: "ok"; resposta: RespostaIA };

export function lerVotos(): Record<string, "util" | "nao_util"> {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_KEY) ?? "{}");
  } catch {
    return {};
  }
}

/** Pede a resposta (POST /resposta) para os resultados na ordem dos cards (#1 = ordem[0]) e devolve
 *  também a posição de cada decisão por id, que o painel "Decisões que sustentam" usa. */
export function useRespostaGerada(estrutura: EstruturaArgumentativa | null, ordem: ResultCard[]) {
  const ids = estrutura ? ordem.slice(0, 20).map((d) => d.id) : [];
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
  const estado: EstadoResposta = pronta
    ? { status: "ok", resposta: pronta }
    : recebida?.chave === chave && recebida.erro !== undefined
      ? { status: "erro", mensagem: recebida.erro }
      : { status: "carregando" };
  return { chave, vazia: ids.length === 0, estado };
}
