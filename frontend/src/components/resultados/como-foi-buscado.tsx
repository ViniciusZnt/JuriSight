"use client";

import { useEffect, useState } from "react";
import { SearchCheck } from "lucide-react";
import { explicarBusca, type EstruturaArgumentativa, type ExplicacaoBusca } from "@/lib/api";

/** Total de acórdãos do acervo (2025), para "N de 69.349 decisões passaram". */
const TOTAL_ACERVO = 69349;

const chipCls = "inline-block px-2.5 py-0.5 mr-1.5 mb-1.5 rounded-lg border";
const chipFiltro = `${chipCls} bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]`;
const chipTermo = `${chipCls} bg-[#FBF4EC] dark:bg-[#2A2015] border-[#EDD9BC] dark:border-[#4A3A22] text-[#6B3B0A] dark:text-[#E0AC6C]`;

function Linha({ cor, titulo, children }: { cor: string; titulo: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[160px_minmax(0,1fr)] gap-1.5 sm:gap-4 py-3.5 border-b last:border-b-0 border-[#E8EEF7] dark:border-[#26313F]">
      <div className="flex items-center gap-2 text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.5px", fontWeight: 700 }}>
        <span className={`w-2 h-2 rounded-sm flex-none ${cor}`} />
        {titulo}
      </div>
      <div className="min-w-0 text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "14.5px", lineHeight: 1.55 }}>
        {children}
      </div>
    </div>
  );
}

/** "Como esta busca foi feita": o que entrou no filtro restrito, na busca semântica e na busca
 *  por termos, em ordem do que mais pesou. Fica aberto, no topo dos resultados, e pede a explicação
 *  ao aparecer (POST /query/explicacao monta os textos a partir da estrutura, sem buscar). */
export function ComoFoiBuscado({
  estrutura,
  filtro,
}: {
  estrutura: EstruturaArgumentativa;
  /** null = busca sem filtro restrito; total null = contagem do acervo indisponível. */
  filtro: { itens: string[]; total: number | null } | null;
}) {
  const [explicacao, setExplicacao] = useState<ExplicacaoBusca | null>(null);
  const [erro, setErro] = useState(false);

  // a página remonta o componente (key) quando a estrutura muda, então basta pedir uma vez
  useEffect(() => {
    let vivo = true;
    explicarBusca(estrutura)
      .then((e) => vivo && setExplicacao(e))
      .catch(() => vivo && setErro(true));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="w-full max-w-[800px] mb-6 rounded-xl border border-[#C8D9EF] dark:border-[#2A3A4C] border-l-4 border-l-[#1A3A5C] dark:border-l-[#8AB0DC] bg-[#F5F8FD] dark:bg-[#131C28] shadow-[0_2px_12px_rgba(26,58,92,0.08)] dark:shadow-none">
      <div className="flex items-start gap-3 px-5 pt-4 pb-2">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#1A3A5C] dark:bg-[#8AB0DC] flex-none">
          <SearchCheck className="w-5 h-5 text-white dark:text-[#131C28]" strokeWidth={1.9} />
        </div>
        <div>
          <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "16.7px", fontWeight: 700 }}>
            Como esta busca foi feita
          </h2>
          <p className="text-[#5A6B80] dark:text-[#9EB0C6]" style={{ fontSize: "13.2px" }}>
            O que foi usado para encontrar as decisões abaixo, do que mais pesou para o que menos pesou.
          </p>
        </div>
      </div>

      <div className="px-5 pb-2">
        {filtro && (
          <Linha cor="bg-[#1A3A5C] dark:bg-[#8AB0DC]" titulo="Filtro restrito">
            <div>
              {filtro.itens.map((i) => (
                <span key={i} className={chipFiltro} style={{ fontSize: "13.5px" }}>{i}</span>
              ))}
            </div>
            {filtro.total !== null && (
              <p className="text-[#5A6B80] dark:text-[#9EB0C6]" style={{ fontSize: "12.6px" }}>
                {`${filtro.total.toLocaleString("pt-BR")} de ${TOTAL_ACERVO.toLocaleString("pt-BR")} decisões passaram; só elas foram ordenadas.`}
              </p>
            )}
          </Linha>
        )}
        {erro && (
          <p className="py-3 text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>
            Não foi possível carregar como a busca foi feita.
          </p>
        )}
        {!erro && !explicacao && (
          <p className="py-3 text-[#5A6B80] dark:text-[#9EB0C6]" style={{ fontSize: "13.2px" }}>Carregando…</p>
        )}
        {explicacao && (
          <>
            <Linha cor="bg-[#6E8FB5]" titulo="Busca semântica">
              {`“${explicacao.semantica}”`}
            </Linha>
            <Linha cor="bg-[#C47A2D]" titulo="Busca por termos">
              {explicacao.termos.length === 0 ? (
                <span className="text-[#5A6B80] dark:text-[#9EB0C6]">Nenhum termo exato: só a busca semântica contou.</span>
              ) : (
                explicacao.termos.map((t) => (
                  <span key={t} className={chipTermo} style={{ fontSize: "13.5px" }}>{t}</span>
                ))
              )}
            </Linha>
          </>
        )}
      </div>
    </section>
  );
}
