"use client";

import { useRef, useState } from "react";
import { ChevronDown, Gauge } from "lucide-react";
import type { UsoAcao } from "@/lib/api";
import { useFecharAoClicarFora } from "@/lib/use-fechar-ao-clicar-fora";
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

const ORDEM_NIVEL: (keyof typeof BARRA)[] = ["normal", "alerta", "esgotado"];

/** A lista "usado / limite" de cada ação, com a barra de cada uma. */
function ListaUso({ acoes }: { acoes: UsoAcao[] }) {
  return (
    <ul className="space-y-2">
      {acoes.map(({ acao, usado, limite }) => {
        const n = nivel(usado, limite);
        const { rotulo, dica } = ROTULOS[acao] ?? { rotulo: acao };
        return (
          <li key={acao} data-nivel={n}>
            <div className="flex items-center justify-between gap-4 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "12.8px" }}>
              <span title={dica}>{rotulo}</span>
              <span className="tabular-nums text-[#6B6B80] dark:text-[#A6A6B4]">{usado} / {limite}</span>
            </div>
            <div className="h-1 rounded-full bg-[#ECECF2] dark:bg-[#26262C] mt-1 overflow-hidden" aria-hidden>
              <div className={`h-full rounded-full ${BARRA[n]}`} style={{ width: `${limite > 0 ? Math.min(100, (100 * usado) / limite) : 0}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** "Uso de hoje" no cabeçalho: um botão com a barra da ação mais gasta; clicar abre o uso de
 *  cada limite diário. Some se GET /uso falhar. */
export function UsoDiarioMenu() {
  const { acoes } = useUsoDiario();
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useFecharAoClicarFora(ref, aberto, () => setAberto(false));
  if (!acoes) return null;

  const fracoes = acoes.map((a) => (a.limite > 0 ? a.usado / a.limite : 0));
  const pior = acoes.reduce((p, a) => {
    const n = nivel(a.usado, a.limite);
    return ORDEM_NIVEL.indexOf(n) > ORDEM_NIVEL.indexOf(p) ? n : p;
  }, "normal" as keyof typeof BARRA);
  const maior = Math.min(1, Math.max(0, ...fracoes));

  return (
    <div ref={ref} className="relative flex-shrink-0" onKeyDown={(e) => e.key === "Escape" && setAberto(false)}>
      <button
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-haspopup="true"
        data-nivel={pior}
        aria-label="Uso de hoje"
        title="Quanto você usou hoje de cada limite diário"
        className="flex items-center gap-2 rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#17171B] px-2.5 py-1.5 text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30 transition-all"
        style={{ fontSize: "12.8px" }}
      >
        <Gauge className="w-3.5 h-3.5" strokeWidth={1.8} />
        <span className="hidden sm:inline">Uso de hoje</span>
        <span className="w-10 h-1 rounded-full bg-[#ECECF2] dark:bg-[#26262C] overflow-hidden" aria-hidden>
          <span className={`block h-full rounded-full ${BARRA[pior]}`} style={{ width: `${100 * maior}%` }} />
        </span>
        <ChevronDown className="w-3 h-3" strokeWidth={2} />
      </button>
      {aberto && (
        <div
          role="dialog"
          aria-label="Uso de hoje"
          className="absolute right-0 top-[calc(100%+6px)] z-30 w-[260px] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] shadow-[0_8px_28px_rgba(0,0,0,0.12)] p-3.5"
        >
          <p className="mb-2.5 text-[#9090A8] dark:text-[#7C7C88] uppercase tracking-[0.06em]" style={{ fontSize: "11px", fontWeight: 600 }}>
            Uso de hoje · renova à meia-noite
          </p>
          <ListaUso acoes={acoes} />
        </div>
      )}
    </div>
  );
}
