import { Info } from "lucide-react";
import type { ResultCard } from "@/lib/api";
import type { Sintese } from "@/lib/sintese";

const ROTULO = "text-[#6B6B80] dark:text-[#A6A6B4] uppercase tracking-[0.06em] mb-1.5";

interface Props {
  sintese: Sintese;
  porId: Map<string, ResultCard>;
  ranks: Map<string, number>;
  citacao: string | null;
  onCitacao: (rotulo: string | null) => void;
  onIr: (id: string) => void;
}

/** Resposta-síntese acima da lista: tendência, base citada (chips que filtram a lista) e as
 *  decisões mais relevantes de cada lado, com âncora para o card. */
export function SinteseResultados({ sintese, porId, ranks, citacao, onCitacao, onIr }: Props) {
  // Com a resposta gerada pronta, os lados são as posições que ela leu (as mesmas decisões que cita).
  const r = sintese.porResposta;
  const lados = [
    { titulo: r ? "Deferiram o pedido" : "A favor do trabalhador", ids: sintese.trabalhador, cor: "text-[#1A5C3A] dark:text-[#6FCB9A]" },
    { titulo: r ? "Negaram pelo direito" : "A favor da empresa", ids: sintese.empresa, cor: "text-[#7A1A1A] dark:text-[#E08A93]" },
    { titulo: "Negaram com outros fatos", ids: sintese.outrosFatos, cor: "text-[#6A6A7A] dark:text-[#9494A2]" },
  ].filter((l) => l.ids.length > 0);

  return (
    <section aria-label="Panorama das decisões" className="w-full mt-1 pt-4 border-t border-[#F0F0F6] dark:border-[#26262C] space-y-4">
      <div>
        <p className={ROTULO} style={{ fontSize: "11.5px", fontWeight: 600 }}>Panorama das decisões</p>
        <p className="text-[#0F1117] dark:text-[#ECECEF] leading-relaxed" style={{ fontSize: "14.9px" }}>
          <strong style={{ fontWeight: 600 }}>{sintese.abertura}</strong> {sintese.tendencia}
        </p>
      </div>

      {sintese.base.length > 0 && (
        <div>
          <p className={ROTULO} style={{ fontSize: "11.5px", fontWeight: 600 }}>Base citada nas decisões</p>
          <div className="flex flex-wrap gap-1.5">
            {sintese.base.map(({ rotulo, ids }) => {
              const ativo = citacao === rotulo;
              return (
                <button
                  key={rotulo}
                  aria-pressed={ativo}
                  onClick={() => onCitacao(ativo ? null : rotulo)}
                  title={ativo ? "Mostrar todas as decisões" : `Mostrar só as decisões que citam ${rotulo}`}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 transition-all ${
                    ativo
                      ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] border-[#1A3A5C] dark:border-[#8AB0DC] text-white dark:text-[#0E0E11]"
                      : "bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC] hover:border-[#1A3A5C]/40"
                  }`}
                  style={{ fontSize: "12.6px", fontWeight: 500 }}
                >
                  {rotulo}
                  <span className="tabular-nums" style={{ fontWeight: 700 }} aria-label={`em ${ids.length} decisões`}>
                    {ids.length}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {lados.length > 0 && (
        <div>
          <p className={ROTULO} style={{ fontSize: "11.5px", fontWeight: 600 }}>Decisões que sustentam</p>
          <ul className="space-y-1">
            {lados.map((l) => (
              <li key={l.titulo} className="flex flex-wrap items-baseline gap-x-3 gap-y-1" style={{ fontSize: "13.8px" }}>
                <span className={l.cor} style={{ fontWeight: 600 }}>{l.titulo}:</span>
                {l.ids.map((id) => {
                  const d = porId.get(id);
                  return (
                    <a
                      key={id}
                      href={`#decisao-${id}`}
                      onClick={() => onIr(id)}
                      className="text-[#1A3A5C] dark:text-[#8AB0DC] underline underline-offset-2 hover:no-underline"
                    >
                      #{ranks.get(id)} {d?.tribunal} · {d?.turma}
                    </a>
                  );
                })}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="flex items-start gap-1.5 text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.6px" }}>
        <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" strokeWidth={1.8} />
        Lado e citações vêm de classificação automática das ementas e podem conter erros. Confira a decisão antes de citar.
      </p>
    </section>
  );
}
