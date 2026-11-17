"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, avaliarLote, type Avaliacao, type EstruturaArgumentativa, type ResultCard } from "@/lib/api";
import { useUsoDiario } from "@/lib/uso-diario";

/** Decisões por chamada a POST /triagem e quantas chamadas ficam em voo ao mesmo tempo. Com 2
 *  em voo, "Parar e responder" ainda economiza: os lotes que não saíram não são pagos. */
export const TAMANHO_LOTE = 10;
export const EM_VOO = 2;

/** avaliando: lotes em voo · parada: o advogado parou, ou sobrou o que avaliar (lote que falhou,
 *  limite diário) · concluida: tudo avaliado · indisponivel: a IA não respondeu ao 1º lote ·
 *  ociosa: conversa reaberta com decisões sem avaliação (nada é gasto sem o clique). */
export type StatusTriagem = "avaliando" | "parada" | "concluida" | "indisponivel" | "ociosa";

interface Estado {
  avaliacoes: Map<string, Avaliacao>;
  /** Decisões sem ementa: a IA não as avalia; contam como processadas, sem nota. */
  semEmenta: Set<string>;
  status: StatusTriagem;
  erro: string | null;
  /** A leitura só do cache (conversa reaberta) terminou: ao voltar à tela, não é refeita. */
  cacheLido?: boolean;
  /** A IA avaliou nesta tela (busca nova ou "Avaliar"): a resposta pode ser refeita com o que ela leu. */
  avaliou?: boolean;
}

// Voltar da página da decisão não refaz (nem cobra) a avaliação: o estado fica por chave.
// "indisponivel" não é final: ao voltar ou reabrir, a avaliação (ou a leitura do cache) é tentada de novo.
const salvos = new Map<string, Estado>();
const TERMINAIS: StatusTriagem[] = ["concluida", "parada", "ociosa"];

function lotes(ids: string[]): string[][] {
  return Array.from({ length: Math.ceil(ids.length / TAMANHO_LOTE) }, (_, i) => ids.slice(i * TAMANHO_LOTE, (i + 1) * TAMANHO_LOTE));
}

function semResposta(e: unknown): boolean {
  return !(e instanceof ApiError) || e.status === 503;
}

/** Avalia os resultados com a IA em lotes (POST /triagem), na ordem do RRF, e devolve as
 *  avaliações à medida que chegam. Busca nova (`automatica`) começa sozinha; reaberta só lê o
 *  cache do servidor e espera `continuar()`. */
export function useTriagem(
  estrutura: EstruturaArgumentativa | null,
  resultados: ResultCard[],
  opcoes: { automatica: boolean },
) {
  const ids = resultados.map((d) => d.id);
  const chave = `${ids.join(",")}|${JSON.stringify(estrutura)}`;

  // Estado inicial de uma chave, sem efeito colateral (calculado no render).
  const inicial = (): Estado => {
    const salvo = salvos.get(chave);
    if (salvo && TERMINAIS.includes(salvo.status)) return salvo;
    const avaliacoes = salvo?.avaliacoes ?? new Map<string, Avaliacao>();
    const semEmenta = salvo?.semEmenta ?? new Set<string>();
    const faltam = ids.some((i) => !avaliacoes.has(i) && !semEmenta.has(i));
    const status: StatusTriagem = !estrutura || !faltam ? "concluida" : opcoes.automatica ? "avaliando" : "ociosa";
    return { avaliacoes, semEmenta, status, erro: null, cacheLido: salvo?.cacheLido, avaliou: !!salvo?.avaliou || status === "avaliando" };
  };

  const [estado, setEstado] = useState<Estado & { chave: string }>(() => ({ chave, ...inicial() }));
  const atual: Estado = estado.chave === chave ? estado : inicial();

  // Cada execução tem um número: resposta de execução antiga (parada, chave trocada) é ignorada.
  const { atualizar: atualizarUso } = useUsoDiario();
  const execucao = useRef(0);
  const controles = useRef(new Set<AbortController>());

  const abortarTudo = useCallback(() => {
    execucao.current += 1;
    controles.current.forEach((c) => c.abort());
    controles.current.clear();
  }, []);

  const atualizar = useCallback(
    (fn: (e: Estado) => Estado) => {
      setEstado((prev) => {
        const novo = { ...fn(prev.chave === chave ? prev : inicial()), chave };
        salvos.set(chave, novo);
        return novo;
      });
    },
    // `chave` resume ids + estrutura; `inicial` só depende deles e de `automatica`
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chave, opcoes.automatica],
  );

  const executar = useCallback(
    (pendentes: string[], modo: "avaliar" | "cache") => {
      if (!estrutura) return;
      abortarTudo();
      const minha = execucao.current;
      const vivo = () => execucao.current === minha;
      const fila = lotes(pendentes).map((loteIds, indice) => ({ ids: loteIds, indice, tentativas: 0 }));
      const limite = modo === "cache" ? fila.length : EM_VOO;
      let emVoo = 0;

      const fim = () => {
        if (!vivo() || fila.length > 0 || emVoo > 0) return;
        atualizar((e) => {
          const faltam = ids.some((i) => !e.avaliacoes.has(i) && !e.semEmenta.has(i));
          return {
            ...e,
            status: !faltam ? "concluida" : modo === "cache" ? "ociosa" : "parada",
            cacheLido: e.cacheLido || modo === "cache",
          };
        });
      };

      const disparar = () => {
        while (vivo() && fila.length > 0 && emVoo < limite) {
          const lote = fila.shift()!;
          const controle = new AbortController();
          controles.current.add(controle);
          emVoo += 1;
          avaliarLote(estrutura, lote.ids, { apenasCache: modo === "cache" }, controle.signal)
            .then(({ avaliacoes: novas, semEmenta }) => {
              emVoo -= 1;
              controles.current.delete(controle);
              if (modo === "avaliar" && !controle.signal.aborted) atualizarUso();
              if (!vivo()) return;
              atualizar((e) => ({
                ...e,
                avaliacoes: new Map([...e.avaliacoes, ...Object.entries(novas)]),
                semEmenta: new Set([...e.semEmenta, ...semEmenta]),
              }));
              disparar();
              fim();
            })
            .catch((err: unknown) => {
              emVoo -= 1;
              controles.current.delete(controle);
              if (modo === "avaliar" && !controle.signal.aborted) atualizarUso();
              if (!vivo()) return;
              if (err instanceof ApiError && err.status === 429) {
                abortarTudo();
                atualizar((e) => ({ ...e, status: "parada", erro: err.message }));
                return;
              }
              if (modo === "avaliar" && lote.tentativas === 0) {
                lote.tentativas += 1;
                fila.unshift(lote);
              } else if (modo === "avaliar" && lote.indice === 0 && semResposta(err)) {
                abortarTudo();
                atualizar((e) => ({ ...e, status: "indisponivel" }));
                return;
              }
              disparar();
              fim();
            });
        }
      };
      disparar();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chave, abortarTudo, atualizar, atualizarUso],
  );

  // Ao montar ou trocar de consulta: avalia (busca nova) ou só lê o cache (reaberta).
  useEffect(() => {
    const inicio = inicial();
    const faltam = ids.filter((i) => !inicio.avaliacoes.has(i) && !inicio.semEmenta.has(i));
    if (inicio.status === "avaliando") executar(faltam, "avaliar");
    else if (inicio.status === "ociosa" && !inicio.cacheLido) executar(faltam, "cache");
    return abortarTudo;
    // `chave` resume ids + estrutura
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  const parar = useCallback(() => {
    abortarTudo();
    atualizar((e) => (e.status === "avaliando" ? { ...e, status: "parada" } : e));
  }, [abortarTudo, atualizar]);

  const continuar = useCallback(() => {
    const faltam = ids.filter((i) => !atual.avaliacoes.has(i) && !atual.semEmenta.has(i));
    if (faltam.length === 0) return;
    atualizar((e) => ({ ...e, status: "avaliando", erro: null, avaliou: true }));
    executar(faltam, "avaliar");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, atual.avaliacoes, atual.semEmenta, atualizar, executar]);

  return {
    avaliacoes: atual.avaliacoes,
    status: atual.status,
    semEmenta: atual.semEmenta,
    /** Processadas: avaliadas pela IA ou sem ementa (que a IA não avalia). */
    avaliadas: ids.filter((i) => atual.avaliacoes.has(i) || atual.semEmenta.has(i)).length,
    total: ids.length,
    erro: atual.erro,
    /** true se a IA avaliou nesta tela; false numa conversa reaberta só com o cache. */
    avaliouAqui: !!atual.avaliou,
    parar,
    continuar,
  };
}
