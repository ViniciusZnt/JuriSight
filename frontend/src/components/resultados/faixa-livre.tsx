"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { queryLivre, type EstruturaArgumentativa, type ResultCard } from "@/lib/api";
import { ResultadoCard } from "@/components/resultados/resultado-card";

interface Props {
  estrutura: EstruturaArgumentativa;
  /** Ids já mostrados na faixa restrita (não repetem aqui). */
  excluir: Set<string>;
  /** Mesmos filtros de desfecho/período/tribunal que a tela aplica à faixa restrita (sem o da base citada). */
  passa: (d: ResultCard) => boolean;
}

/** Faixa "Busca livre (sem o filtro)": fechada, busca só na primeira abertura. Não entra em
 *  `resultados`, na conversa salva nem na resposta gerada. */
export function FaixaLivre({ estrutura, excluir, passa }: Props) {
  const [aberta, setAberta] = useState(false);
  const [cards, setCards] = useState<ResultCard[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const alternar = () => {
    setAberta((v) => !v);
    if (aberta || cards !== null || carregando) return;
    setCarregando(true);
    setErro(null);
    queryLivre({ estrutura })
      .then(setCards)
      .catch((e: Error) => setErro(e.message))
      .finally(() => setCarregando(false));
  };

  const visiveis = (cards ?? []).filter((d) => !excluir.has(d.id) && passa(d));

  return (
    <section className="w-full max-w-[800px] mt-8">
      <button
        onClick={alternar}
        aria-expanded={aberta}
        className="flex items-center gap-2 text-[#1A3A5C] dark:text-[#8AB0DC]"
        style={{ fontSize: "16.7px", fontWeight: 600 }}
      >
        Busca livre (sem o filtro)
        <ChevronDown className={`w-4 h-4 transition-transform ${aberta ? "rotate-180" : ""}`} strokeWidth={2} />
      </button>
      <p className="text-[#8A8A9A] dark:text-[#9494A2] mb-3" style={{ fontSize: "13.8px" }}>
        Decisões parecidas, sem garantia de citar os dispositivos ou conter as expressões.
      </p>
      {aberta && (
        <div className="space-y-4">
          {carregando && <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>Buscando…</p>}
          {erro && <p className="text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "13.8px" }}>{erro}</p>}
          {cards !== null && visiveis.length === 0 && (
            <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.8px" }}>Nenhuma decisão além das já mostradas acima.</p>
          )}
          {visiveis.map((d) => (
            <ResultadoCard key={d.id} decision={d} estrutura={estrutura} idPrefix="livre" />
          ))}
        </div>
      )}
    </section>
  );
}
