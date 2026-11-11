"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { explicarBusca, type EstruturaArgumentativa, type ExplicacaoBusca } from "@/lib/api";

/** Total de acórdãos do acervo (2025), para "N de 69.349 decisões passaram". */
const TOTAL_ACERVO = 69349;

const chipCls = "inline-block px-2.5 py-0.5 mr-1.5 mb-1.5 rounded-lg border";
const chipFiltro = `${chipCls} bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]`;
const chipTermo = `${chipCls} bg-[#FBF4EC] dark:bg-[#2A2015] border-[#EDD9BC] dark:border-[#4A3A22] text-[#6B3B0A] dark:text-[#E0AC6C]`;

function Linha({ cor, titulo, children }: { cor: string; titulo: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[150px_minmax(0,1fr)] gap-1.5 sm:gap-4 py-3 border-b last:border-b-0 border-[#F4F4F8] dark:border-[#26262C]">
      <div className="flex items-center gap-2 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13px", fontWeight: 600 }}>
        <span className={`w-2 h-2 rounded-sm flex-none ${cor}`} />
        {titulo}
      </div>
      <div className="min-w-0 text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "14px", lineHeight: 1.5 }}>
        {children}
      </div>
    </div>
  );
}

/** "Como esta busca foi feita": o que entrou no filtro restrito, na busca semântica e na busca
 *  por termos, em ordem do que mais pesou. Fechado por padrão; a explicação só é pedida ao abrir
 *  (POST /query/explicacao monta os textos a partir da estrutura, sem buscar). */
export function ComoFoiBuscado({
  estrutura,
  filtro,
}: {
  estrutura: EstruturaArgumentativa;
  /** null = busca sem filtro restrito; total null = contagem do acervo indisponível. */
  filtro: { itens: string[]; total: number | null } | null;
}) {
  const [aberto, setAberto] = useState(false);
  const [explicacao, setExplicacao] = useState<ExplicacaoBusca | null>(null);
  const [erro, setErro] = useState(false);

  const alternar = () => {
    const abrir = !aberto;
    setAberto(abrir);
    if (abrir && !explicacao) {
      setErro(false);
      explicarBusca(estrutura)
        .then(setExplicacao)
        .catch(() => setErro(true));
    }
  };

  return (
    <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_2px_12px_rgba(0,0,0,0.06)] dark:shadow-none mb-6">
      <button
        onClick={alternar}
        aria-expanded={aberto}
        className="w-full flex items-center justify-between gap-3 px-5 py-3.5 text-left"
      >
        <span className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "15px", fontWeight: 600 }}>
          Como esta busca foi feita
        </span>
        <span className="flex items-center gap-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13px" }}>
          {aberto ? "Fechar" : "Ver"}
          <ChevronDown className={`w-4 h-4 transition-transform ${aberto ? "rotate-180" : ""}`} />
        </span>
      </button>

      {aberto && (
        <div className="px-5 pb-3 border-t border-[#F0F0F6] dark:border-[#26262C]">
          {filtro && (
            <Linha cor="bg-[#1A3A5C] dark:bg-[#8AB0DC]" titulo="Filtro restrito">
              <div>
                {filtro.itens.map((i) => (
                  <span key={i} className={chipFiltro} style={{ fontSize: "13.5px" }}>{i}</span>
                ))}
              </div>
              {filtro.total !== null && (
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
                  {`${filtro.total.toLocaleString("pt-BR")} de ${TOTAL_ACERVO.toLocaleString("pt-BR")} decisões passaram; só elas foram ordenadas.`}
                </p>
              )}
            </Linha>
          )}
          {erro && (
            <p className="py-3 text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>
              Não foi possível carregar como a busca foi feita. Tente abrir de novo.
            </p>
          )}
          {!erro && !explicacao && (
            <p className="py-3 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>Carregando…</p>
          )}
          {explicacao && (
            <>
              <Linha cor="bg-[#6E8FB5]" titulo="Busca semântica">
                {`“${explicacao.semantica}”`}
              </Linha>
              <Linha cor="bg-[#C47A2D]" titulo="Busca por termos">
                {explicacao.termos.length === 0 ? (
                  <span className="text-[#8A8A9A] dark:text-[#9494A2]">Nenhum termo exato.</span>
                ) : (
                  explicacao.termos.map((t) => (
                    <span key={t} className={chipTermo} style={{ fontSize: "13.5px" }}>{t}</span>
                  ))
                )}
              </Linha>
            </>
          )}
        </div>
      )}
    </div>
  );
}
