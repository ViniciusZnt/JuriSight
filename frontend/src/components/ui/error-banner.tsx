"use client";

import { AlertCircle, RotateCw } from "lucide-react";

/** Erro de chamada à API (rede ou HTTP) — não é nenhum FA da RFC, só uma falha
 *  de comunicação com o backend. Tom neutro/vermelho, distinto do amber
 *  reservado à FA02. */
export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="w-full max-w-[720px] mx-auto flex items-start gap-3 rounded-xl border border-[#E8C2C2] dark:border-[#4A2529] bg-[#FBF0F0] dark:bg-[#2A1517] px-4 py-3">
      <AlertCircle className="w-4 h-4 text-[#C44040] dark:text-[#D96B6B] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
      <div className="flex-1 min-w-0">
        <p className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.8px" }}>
          {message}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 mt-2 text-[#7A1A1A] dark:text-[#E08A93] hover:underline"
            style={{ fontSize: "13.2px", fontWeight: 600 }}
          >
            <RotateCw className="w-3 h-3" strokeWidth={2} />
            Tentar novamente
          </button>
        )}
      </div>
    </div>
  );
}
