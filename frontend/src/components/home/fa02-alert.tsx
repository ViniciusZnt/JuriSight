"use client";

import { AlertTriangle, RefreshCw, ArrowRight, X } from "lucide-react";

/** FA02 — PDF sem texto extraível (RFC 3.2). Aparece dentro da caixa de consulta quando o
 *  sistema não consegue extrair texto do PDF enviado (documento escaneado/imagem). Deixa o
 *  usuário reenviar outro arquivo ou seguir sem PDF (mesmo fluxo da FA01). */
export function Fa02Alert({
  fileName,
  message,
  onRetry,
  onContinueWithoutFile,
  onDismiss,
}: {
  fileName: string;
  /** Aviso real devolvido por POST /enrich (EnrichResponse.aviso) quando pdf_extraido === false. */
  message: string;
  onRetry: () => void;
  onContinueWithoutFile: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="w-full max-w-[720px] mx-auto mt-3 rounded-2xl border border-[#EDD9BC] dark:border-[#4A3A22] bg-[#FBF4EC] dark:bg-[#2A2015] px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/70 dark:bg-black/20 flex-shrink-0">
          <AlertTriangle className="w-4 h-4 text-[#8A5A1E] dark:text-[#E0AC6C]" strokeWidth={1.8} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[#6B3B0A] dark:text-[#E0AC6C]" style={{ fontSize: "14.4px", fontWeight: 600 }}>
            Não foi possível extrair texto de &ldquo;{fileName}&rdquo;
          </p>
          <p className="text-[#8A5A1E] dark:text-[#C9A26E] mt-1 leading-relaxed" style={{ fontSize: "13.8px" }}>
            {message}
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <button
              onClick={onRetry}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#8A5A1E] dark:bg-[#C98A3D] text-white hover:bg-[#6B3B0A] dark:hover:bg-[#B37A2D] transition-colors"
              style={{ fontSize: "13.2px", fontWeight: 600 }}
            >
              <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.8} />
              Reenviar arquivo
            </button>
            <button
              onClick={onContinueWithoutFile}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#DCCAAC] dark:border-[#4A3A22] text-[#6B3B0A] dark:text-[#E0AC6C] hover:bg-white/60 dark:hover:bg-black/20 transition-colors"
              style={{ fontSize: "13.2px", fontWeight: 500 }}
            >
              Continuar sem o PDF
              <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.8} />
            </button>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-[#B08A5A] dark:text-[#8A6E4A] hover:text-[#6B3B0A] dark:hover:text-[#E0AC6C] transition-colors flex-shrink-0"
          title="Fechar"
          aria-label="Fechar"
        >
          <X className="w-3.5 h-3.5" strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
