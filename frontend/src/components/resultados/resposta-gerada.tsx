"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Copy, Info, ThumbsDown, ThumbsUp } from "lucide-react";
import { ActionButton } from "@/components/ui/action-button";
import { gerarResposta, type EstruturaArgumentativa, type FraseResposta, type RespostaIA, type ResultCard } from "@/lib/api";
import { formatarData, respostaParaCopiar } from "@/lib/decision-view";
import { copiarTexto } from "@/lib/utils";

const FEEDBACK_KEY = "jurisight:feedback-resposta";
// Voltar da decisão para a lista não gera (nem cobra) a resposta de novo.
const cache = new Map<string, RespostaIA>();

export type EstadoResposta = { status: "carregando" } | { status: "erro"; mensagem: string } | { status: "ok"; resposta: RespostaIA };

function lerVotos(): Record<string, "util" | "nao_util"> {
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

// Parágrafos: resposta direta (negrito) | fundamento | base legal | o que provar | divergência.
const PARAGRAFO: Record<FraseResposta["tipo"], number> = { resposta: 0, fundamento: 1, base_legal: 2, prova: 3, divergencia: 4 };

interface Props {
  resposta: ReturnType<typeof useRespostaGerada>;
  /** Resultados na ordem da numeração dos cards (#1 = ordem[0]). */
  ordem: ResultCard[];
  onIr: (id: string) => void;
}

/** Resposta gerada por IA a partir das ementas listadas: cada frase com chips "#n" que levam ao
 *  card, e abaixo as fontes (as decisões citadas). Some quando não há frase ancorada; em erro, só
 *  uma linha discreta. */
export function RespostaGerada({ resposta: { chave, vazia, estado }, ordem, onIr }: Props) {
  const [copiada, setCopiada] = useState(false);
  const [votos, setVotos] = useState(lerVotos);
  const voto = votos[chave];

  if (vazia || (estado.status === "ok" && estado.resposta.frases.length === 0)) return null;

  if (estado.status === "erro") {
    return (
      <p role="status" className="w-full max-w-[800px] mb-3 flex items-center gap-1.5 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
        <Info className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={1.8} />
        Resposta gerada indisponível: {estado.mensagem}
      </p>
    );
  }

  const porNumero = new Map(ordem.map((d, i) => [i + 1, d]));
  const votar = (v: "util" | "nao_util") => {
    const novos = { ...lerVotos() };
    if (voto === v) delete novos[chave];
    else novos[chave] = v;
    setVotos(novos);
    try {
      localStorage.setItem(FEEDBACK_KEY, JSON.stringify(novos));
    } catch {
      /* localStorage indisponível: o voto vale só nesta tela */
    }
  };

  const frase = (f: FraseResposta, i: number) => (
    <span key={i}>
      {f.texto}{" "}
      {f.citacoes.map((n) => {
        const d = porNumero.get(n);
        return (
          <a
            key={n}
            href={d ? `#decisao-${d.id}` : undefined}
            onClick={() => d && onIr(d.id)}
            title={d ? `${d.tribunal} · ${d.turma} · ${d.numero_processo}` : undefined}
            className="inline-flex items-center align-baseline mr-1 px-1.5 rounded-md bg-[#EEF3FB] dark:bg-[#1A2A3C] border border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC] hover:border-[#1A3A5C]/50 no-underline tabular-nums"
            style={{ fontSize: "12.1px", fontWeight: 600, fontStyle: "normal" }}
          >
            #{n}
          </a>
        );
      })}{" "}
    </span>
  );
  const frases = estado.status === "ok" ? estado.resposta.frases : [];
  const paragrafos = [0, 1, 2, 3, 4].map((p) => frases.map((f, i) => [f, i] as const).filter(([f]) => PARAGRAFO[f.tipo] === p)).filter((p) => p.length > 0);
  const fontes = [...new Set(frases.flatMap((f) => f.citacoes))].sort((a, b) => a - b).filter((n) => porNumero.has(n));

  return (
    <section
      aria-label="Resposta"
      aria-busy={estado.status === "carregando"}
      className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none px-6 py-5 mb-4"
    >
      <p className="text-[#6B6B80] dark:text-[#A6A6B4] uppercase tracking-[0.06em] mb-2" style={{ fontSize: "11.5px", fontWeight: 600 }}>
        Resposta
      </p>

      {estado.status === "carregando" ? (
        <div className="space-y-2.5 animate-pulse" aria-label="Gerando a resposta a partir das decisões…">
          {["w-full", "w-11/12", "w-full", "w-3/4"].map((w, i) => (
            <div key={i} className={`h-3.5 rounded bg-[#EEEEF3] dark:bg-[#26262C] ${w}`} />
          ))}
        </div>
      ) : (
        <>
          <div className="space-y-3 text-[#0F1117] dark:text-[#ECECEF] leading-relaxed" style={{ fontSize: "14.9px" }}>
            {paragrafos.map((p, k) => (
              <p key={k} style={p[0][0].tipo === "resposta" ? { fontWeight: 600 } : undefined}>
                {/* a base legal não sai das ementas (por isso não tem chip): o rótulo diz de onde vem */}
                {p[0][0].tipo === "base_legal" && (
                  <span className="text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontWeight: 600 }}>
                    Base legal:{" "}
                  </span>
                )}
                {p.map(([f, i]) => frase(f, i))}
              </p>
            ))}
          </div>

          {/* Fontes: as decisões citadas, cada uma leva ao card (como os chips) */}
          <div className="mt-4 pt-3 border-t border-[#F0F0F6] dark:border-[#26262C]">
            <p className="text-[#6B6B80] dark:text-[#A6A6B4] uppercase tracking-[0.06em] mb-1.5" style={{ fontSize: "11.5px", fontWeight: 600 }}>
              Fontes
            </p>
            <ol className="space-y-1" style={{ fontSize: "12.6px" }}>
              {fontes.map((n) => {
                const d = porNumero.get(n)!;
                return (
                  <li key={n} className="min-w-0">
                    <a
                      href={`#decisao-${d.id}`}
                      onClick={() => onIr(d.id)}
                      className="group/fonte flex gap-1.5 text-[#4A4A5A] dark:text-[#C4C4CE] no-underline"
                    >
                      <span className="flex-shrink-0 text-[#1A3A5C] dark:text-[#8AB0DC] tabular-nums" style={{ fontWeight: 600 }}>#{n}</span>
                      <span className="min-w-0 break-words group-hover/fonte:underline underline-offset-2">
                        {[d.sigla_classe, d.tribunal, d.turma, d.data_julgamento && formatarData(d.data_julgamento), d.numero_processo].filter(Boolean).join(" · ")}
                      </span>
                    </a>
                  </li>
                );
              })}
            </ol>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-4">
            <ActionButton
              icon={copiada ? CheckCircle2 : Copy}
              label={copiada ? "Copiada!" : "Copiar resposta"}
              tone={copiada ? "success" : "neutral"}
              size="sm"
              title="Copiar a resposta com as citações (tribunal, turma, processo, data)"
              onClick={() =>
                copiarTexto(respostaParaCopiar(frases, porNumero)).then(() => {
                  setCopiada(true);
                  setTimeout(() => setCopiada(false), 2000);
                })
              }
            />
            {(
              [
                ["util", ThumbsUp, "Resposta útil"],
                ["nao_util", ThumbsDown, "Resposta não útil"],
              ] as const
            ).map(([v, Icone, rotulo]) => (
              <button
                key={v}
                onClick={() => votar(v)}
                aria-pressed={voto === v}
                aria-label={rotulo}
                title={rotulo}
                className={`flex items-center justify-center w-[30px] h-[30px] rounded-lg border transition-all ${
                  voto === v
                    ? "bg-[#EFF4FA] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]"
                    : "bg-[#FAFAFA] dark:bg-[#1C1C21] border-[#EBEBF2] dark:border-[#26262C] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30"
                }`}
              >
                <Icone className="w-3.5 h-3.5" strokeWidth={1.8} fill={voto === v ? "currentColor" : "none"} />
              </button>
            ))}
          </div>
        </>
      )}

      <p className="flex items-start gap-1.5 mt-3 text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.6px" }}>
        <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" strokeWidth={1.8} />
        Resposta gerada por IA a partir das decisões listadas; confira as citações.
      </p>
    </section>
  );
}
