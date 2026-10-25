"use client";

import { Loader2 } from "lucide-react";

/** FA05 — documento extenso, acima do limite de contexto do LLM (RFC 3.2). Some sozinha quando
 *  a Home navega para a revisão; é só o feedback visual da sumarização hierárquica automática. */
export function Fa05Processing({ fileName }: { fileName: string }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px] px-6">
      <div className="w-full max-w-sm rounded-2xl bg-white dark:bg-[#17171B] border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_8px_40px_rgba(0,0,0,0.18)] px-6 py-7 text-center">
        <div className="mx-auto mb-4 flex items-center justify-center w-11 h-11 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C]">
          <Loader2 className="w-5 h-5 text-[#1A3A5C] dark:text-[#8AB0DC] animate-spin" strokeWidth={2} />
        </div>
        <p className="text-[#0F1117] dark:text-[#ECECEF] mb-1.5" style={{ fontSize: "15.5px", fontWeight: 600 }}>
          Documento extenso detectado
        </p>
        <p className="text-[#8A8A9A] dark:text-[#9494A2] leading-relaxed" style={{ fontSize: "13.8px" }}>
          Processando &ldquo;{fileName}&rdquo; em blocos para garantir que nenhuma informação relevante seja
          perdida…
        </p>
      </div>
    </div>
  );
}
