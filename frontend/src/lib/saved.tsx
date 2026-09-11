"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
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

const STORAGE_KEY = "jurisight:saved";

interface SavedCtx {
  saved: SavedDecision[];
  isSaved: (id: string) => boolean;
  toggle: (decision: Omit<SavedDecision, "savedAt">) => void;
}

const Ctx = createContext<SavedCtx | null>(null);

export function SavedProvider({ children }: { children: React.ReactNode }) {
  const [saved, setSaved] = useState<SavedDecision[]>([]);
  const [hydrated, setHydrated] = useState(false);

  // Carrega do localStorage uma vez (client-only).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* storage indisponível — segue vazio */
    }
    setHydrated(true);
  }, []);

  // Persiste a cada mudança (só depois de hidratar, p/ não sobrescrever com []).
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    } catch {
      /* ignora */
    }
  }, [saved, hydrated]);

  const isSaved = useCallback((id: string) => saved.some((s) => s.id === id), [saved]);

  const toggle = useCallback((decision: Omit<SavedDecision, "savedAt">) => {
    setSaved((prev) =>
      prev.some((s) => s.id === decision.id)
        ? prev.filter((s) => s.id !== decision.id)
        : [{ ...decision, savedAt: Date.now() }, ...prev]
    );
  }, []);

  return <Ctx.Provider value={{ saved, isSaved, toggle }}>{children}</Ctx.Provider>;
}

export function useSaved() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSaved precisa de <SavedProvider>.");
  return ctx;
}
