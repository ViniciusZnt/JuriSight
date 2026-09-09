"use client";

import { Loader2 } from "lucide-react";

/** Overlay de carregamento enquanto POST /enrich está em voo. Genérico —
 *  a sumarização hierárquica de PDFs longos (FA04) é transparente dentro do
 *  próprio /enrich, então não há mais um sinal client-side de "arquivo
 *  grande" para mostrar uma mensagem diferente. */
export function AnalyzingOverlay({ fileName }: { fileName: string | null }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px] px-6">
      <div className="w-full max-w-sm rounded-2xl bg-white dark:bg-[#17171B] border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_8px_40px_rgba(0,0,0,0.18)] px-6 py-7 text-center">
        <div className="mx-auto mb-4 flex items-center justify-center w-11 h-11 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C]">
          <Loader2 className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC] animate-spin" strokeWidth={2} />
        </div>
        <p className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
          Analisando sua consulta
        </p>
        <p className="text-[#8A8A9A] dark:text-[#9494A2] leading-relaxed" style={{ fontSize: "13.8px" }}>
          {fileName
            ? <>Extraindo o contexto jurídico de &ldquo;{fileName}&rdquo;…</>
            : "Identificando o contexto jurídico da sua intenção argumentativa…"}
        </p>
      </div>
    </div>
  );
}
