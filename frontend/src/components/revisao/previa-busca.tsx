"use client";

import { useEffect, useState } from "react";
import { ApiError, explicarBusca, rotuloTribunal, ROTULO_FASE, type EstruturaArgumentativa, type ExplicacaoBusca } from "@/lib/api";
import { BUSCA } from "@/lib/cores-busca";

const ESPERA_MS = 400;

type Estado = { tipo: "ok"; explicacao: ExplicacaoBusca } | { tipo: "vazia" } | { tipo: "oculta" };

function Linha({ rotulo, ponto, children }: { rotulo: string; ponto: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-1">
      <span className="flex items-center gap-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "12.6px", fontWeight: 600 }}>
        <span className={`w-2 h-2 rounded-sm ${ponto}`} />
        {rotulo}
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Chips({ itens, estilo }: { itens: string[]; estilo: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {itens.map((t) => (
        <span key={t} className={`inline-block rounded-md border px-2 leading-6 ${estilo}`} style={{ fontSize: "12.8px" }}>
          {t}
        </span>
      ))}
    </div>
  );
}

/** "O que esta busca vai usar": o mesmo que "Como esta busca foi feita" mostra nos resultados
 *  (POST /query/explicacao, sem IA), mas antes de buscar e atualizado enquanto se edita. */
export function PreviaBusca({ estrutura }: { estrutura: EstruturaArgumentativa }) {
  const [estado, setEstado] = useState<Estado>({ tipo: "oculta" });
  const chave = JSON.stringify(estrutura);

  useEffect(() => {
    let vivo = true;
    const espera = setTimeout(() => {
      explicarBusca(estrutura)
        .then((explicacao) => vivo && setEstado({ tipo: "ok", explicacao }))
        .catch((e: unknown) => vivo && setEstado(e instanceof ApiError && e.status === 422 ? { tipo: "vazia" } : { tipo: "oculta" }));
    }, ESPERA_MS);
    return () => {
      vivo = false; // resposta de uma edição anterior não sobrescreve a atual
      clearTimeout(espera);
    };
    // `chave` resume a estrutura
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  if (estado.tipo === "oculta") return null;

  const exige =
    estado.tipo === "ok"
      ? [
          ...estado.explicacao.dispositivos,
          ...estrutura.expressoes.map((e) => `“${e}”`),
          ...estrutura.tribunais.map(rotuloTribunal),
          ...(estrutura.fase ? [ROTULO_FASE[estrutura.fase]] : []),
        ]
      : [];

  return (
    <section aria-label="O que esta busca vai usar" className="p-4 rounded-xl border border-[#E8E8F0] dark:border-[#26262C] bg-[#FAFBFF] dark:bg-[#15191F]">
      <p className="mb-3 text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
        O que esta busca vai usar
      </p>
      {estado.tipo === "vazia" ? (
        <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.4px" }}>
          Preencha a tese central ou o pedido principal para buscar
        </p>
      ) : (
        <div className="space-y-2.5">
          <Linha rotulo="Pelos termos" ponto={BUSCA.termos.ponto}>
            {estado.explicacao.termos.length ? (
              <Chips itens={estado.explicacao.termos} estilo={BUSCA.termos.chip} />
            ) : (
              <span className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.8px" }}>Nenhum termo exato: só a busca pelo sentido conta.</span>
            )}
          </Linha>
          <Linha rotulo="Pelo sentido" ponto={BUSCA.semantica.ponto}>
            <p className="text-[#33333F] dark:text-[#D4D4DC] leading-relaxed" style={{ fontSize: "13.4px" }}>
              {estado.explicacao.semantica}
            </p>
          </Linha>
          <Linha rotulo="Exige" ponto={BUSCA.filtro.ponto}>
            {exige.length ? (
              <Chips itens={exige} estilo={BUSCA.filtro.chip} />
            ) : (
              <span className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.8px" }}>Nada é exigido: todo o acervo entra</span>
            )}
          </Linha>
        </div>
      )}
    </section>
  );
}
