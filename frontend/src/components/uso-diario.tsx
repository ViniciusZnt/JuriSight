"use client";

import { useUsoDiario } from "@/lib/uso-diario";

const ROTULOS: Record<string, { rotulo: string; dica?: string }> = {
  enrich: { rotulo: "Leitura do caso" },
  query: { rotulo: "Buscas" },
  triagem: { rotulo: "Avaliações da IA", dica: "Cada lote de até 10 decisões conta 1" },
  resposta: { rotulo: "Respostas da IA" },
};

const BARRA = {
  normal: "bg-[#1A3A5C] dark:bg-[#8AB0DC]",
  alerta: "bg-[#C98A2B] dark:bg-[#E0AC6C]",
  esgotado: "bg-[#C44040] dark:bg-[#D96B6B]",
};

function nivel(usado: number, limite: number): keyof typeof BARRA {
  if (limite > 0 && usado >= limite) return "esgotado";
  if (limite > 0 && usado / limite >= 0.8) return "alerta";
  return "normal";
}

/** "Uso de hoje" no rodapé da sidebar: quanto a conta gastou de cada limite diário. */
export function UsoDiarioIndicador() {
  const { acoes } = useUsoDiario();
  if (!acoes) return null;
  return (
    <section aria-label="Uso de hoje" className="px-2 pt-1 pb-2">
      <p className="mb-1.5 text-[#9090A8] dark:text-[#7C7C88] uppercase tracking-[0.06em]" style={{ fontSize: "11px", fontWeight: 600 }}>
        Uso de hoje
      </p>
      <ul className="space-y-1.5">
        {acoes.map(({ acao, usado, limite }) => {
          const n = nivel(usado, limite);
          const { rotulo, dica } = ROTULOS[acao] ?? { rotulo: acao };
          return (
            <li key={acao} data-nivel={n}>
              <div className="flex items-center justify-between text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12px" }}>
                <span title={dica}>{rotulo}</span>
                <span className="tabular-nums">{usado} / {limite}</span>
              </div>
              <div className="h-1 rounded-full bg-[#ECECF2] dark:bg-[#26262C] mt-0.5 overflow-hidden" aria-hidden>
                <div className={`h-full rounded-full ${BARRA[n]}`} style={{ width: `${limite > 0 ? Math.min(100, (100 * usado) / limite) : 0}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
