"use client";

import { AlertTriangle, Sparkles } from "lucide-react";
import { PARAR_COM_MESMO_FATO, type StatusTriagem } from "@/components/resultados/triagem";

interface Props {
  status: StatusTriagem;
  avaliadas: number;
  total: number;
  erro: string | null;
  /** Parou sozinha ao achar decisões suficientes com o mesmo problema e fato. */
  paradaAutomatica?: boolean;
  onParar: () => void;
  onContinuar: () => void;
}

/** Barra da triagem por IA acima da lista: progresso e "Parar e responder" enquanto avalia;
 *  "Avaliar N restantes" quando sobrou o que avaliar; aviso quando a IA não respondeu. */
export function ProgressoTriagem({ status, avaliadas, total, erro, paradaAutomatica, onParar, onContinuar }: Props) {
  const restantes = total - avaliadas;
  const caixa = "w-full max-w-[800px] mb-4 flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3";

  if (status === "indisponivel") {
    return (
      <div role="status" className={`${caixa} border-[#EDD9BC] dark:border-[#4A3A22] bg-[#FBF4EC] dark:bg-[#2A2015]`}>
        <AlertTriangle className="w-4 h-4 text-[#8A5A1E] dark:text-[#E0AC6C] flex-shrink-0" strokeWidth={1.8} />
        <p className="flex-1 min-w-[180px] text-[#6B3B0A] dark:text-[#E0AC6C]" style={{ fontSize: "13.8px" }}>
          Avaliação por IA indisponível agora; a lista está na ordem da busca.
        </p>
        <button
          onClick={onContinuar}
          className="rounded-lg border border-[#EDD9BC] dark:border-[#4A3A22] bg-white dark:bg-[#17171B] text-[#8A5A1E] dark:text-[#E0AC6C] px-3 py-1.5 hover:border-[#8A5A1E]/40 transition-colors"
          style={{ fontSize: "13px", fontWeight: 600 }}
        >
          Tentar de novo
        </button>
      </div>
    );
  }
  if (status === "concluida" || (restantes === 0 && !erro)) return null;

  const avaliando = status === "avaliando";
  return (
    <div
      role="status"
      aria-busy={avaliando}
      className={`${caixa} border-[#C8D9EF] dark:border-[#2A3A4C] bg-[#F5F8FD] dark:bg-[#131C28]`}
    >
      <Sparkles className="w-4 h-4 text-[#1A3A5C] dark:text-[#8AB0DC] flex-shrink-0" strokeWidth={1.8} />
      <div className="flex-1 min-w-[180px]">
        <p className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.8px", fontWeight: 600 }}>
          {avaliando
            ? `Avaliando decisões com a IA… ${avaliadas} de ${total}`
            : paradaAutomatica
              ? `Parou ao encontrar ${PARAR_COM_MESMO_FATO} decisões com o mesmo problema e fato · ${restantes} não avaliadas`
              : `${restantes} ${restantes === 1 ? "decisão ainda não avaliada" : "decisões ainda não avaliadas"}`}
        </p>
        {avaliando && (
          <div className="h-1 rounded-full bg-[#DCE6F3] dark:bg-[#26313F] mt-1.5 overflow-hidden" aria-hidden>
            <div className="h-full rounded-full bg-[#1A3A5C] dark:bg-[#8AB0DC] transition-all" style={{ width: `${total ? (100 * avaliadas) / total : 0}%` }} />
          </div>
        )}
        {erro && <p className="mt-1 text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "12.8px" }}>{erro}</p>}
      </div>
      {avaliando ? (
        <button
          onClick={onParar}
          className="rounded-lg bg-[#1A3A5C] text-white px-3 py-1.5 hover:bg-[#1E4570] transition-colors"
          style={{ fontSize: "13px", fontWeight: 600 }}
        >
          Parar e responder
        </button>
      ) : (
        restantes > 0 && (
          <button
            onClick={onContinuar}
            className="rounded-lg border border-[#C8D9EF] dark:border-[#2A3A4C] bg-white dark:bg-[#17171B] text-[#1A3A5C] dark:text-[#8AB0DC] px-3 py-1.5 hover:border-[#1A3A5C]/40 transition-colors"
            style={{ fontSize: "13px", fontWeight: 600 }}
          >
            Avaliar {restantes} restantes
          </button>
        )
      )}
    </div>
  );
}
