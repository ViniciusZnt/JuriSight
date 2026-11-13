"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useAuth } from "@/lib/auth";
import type { Outcome } from "@/lib/outcome";

/** Um acórdão salvo pelo usuário (UC "Salvar", botão presente nos resultados e no detalhe). */
export interface SavedDecision {
  id: string;
  title: string;
  court: string;
  chamber: string;
  date: string;
  outcome: Outcome;
  relevance: number;
  rapporteur: string;
  processNumber: string;
  savedAt: number; // epoch ms
}

/** Salvos ficam no navegador, separados por usuário (como o perfil): outra conta no mesmo
 *  navegador não vê a lista da anterior. */
const chaveDe = (usuarioId: string) => `jurisight:saved:${usuarioId}`;

interface SavedCtx {
  saved: SavedDecision[];
  isSaved: (id: string) => boolean;
  toggle: (decision: Omit<SavedDecision, "savedAt">) => void;
}

const Ctx = createContext<SavedCtx | null>(null);

export function SavedProvider({ children }: { children: React.ReactNode }) {
  const { usuario } = useAuth();
  const usuarioId = usuario?.id ?? null;
  const [saved, setSaved] = useState<SavedDecision[]>([]);

  // Recarrega a cada troca de conta; sem sessão, a lista fica vazia.
  useEffect(() => {
    setSaved([]);
    if (!usuarioId) return;
    try {
      const raw = localStorage.getItem(chaveDe(usuarioId));
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* storage indisponível — segue vazio */
    }
  }, [usuarioId]);

  const isSaved = useCallback((id: string) => saved.some((s) => s.id === id), [saved]);

  // Grava junto com a mudança, na chave da conta atual (um efeito separado poderia gravar a
  // lista da conta anterior na chave da nova, durante a troca).
  const toggle = useCallback(
    (decision: Omit<SavedDecision, "savedAt">) => {
      setSaved((prev) => {
        const novo = prev.some((s) => s.id === decision.id)
          ? prev.filter((s) => s.id !== decision.id)
          : [{ ...decision, savedAt: Date.now() }, ...prev];
        if (usuarioId) {
          try {
            localStorage.setItem(chaveDe(usuarioId), JSON.stringify(novo));
          } catch {
            /* ignora */
          }
        }
        return novo;
      });
    },
    [usuarioId]
  );

  return <Ctx.Provider value={{ saved, isSaved, toggle }}>{children}</Ctx.Provider>;
}

export function useSaved() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSaved precisa de <SavedProvider>.");
  return ctx;
}
