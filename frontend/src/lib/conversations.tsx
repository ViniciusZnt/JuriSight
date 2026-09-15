"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { EstruturaArgumentativa, ResultCard } from "@/lib/api";

/** Snapshot do que essa conversa já produziu — o suficiente pra reabrir exatamente de
 *  onde parou (Revisão, se só enriqueceu; Resultados, se já buscou). Persistido só no
 *  navegador (localStorage), igual ao resto do app — ver RFC §6.1 (LGPD): nada disso
 *  é enviado/guardado no backend. */
export interface ConversationSnapshot {
  estrutura: EstruturaArgumentativa;
  hasFile: boolean;
  fileName: string | null;
  pdfExtraido: boolean | null;
  aviso: string | null;
  resultados: ResultCard[] | null;
}

/** Uma pesquisa salva (o "histórico" da sidebar). */
export interface Conversation {
  id: string;
  title: string;
  createdAt: number; // epoch ms
  snapshot?: ConversationSnapshot;
}

const STORAGE_KEY = "jurisight:conversations";

interface ConversationsCtx {
  conversations: Conversation[];
  activeId: string | null;
  create: (title: string) => string; // devolve o id novo
  rename: (id: string, title: string) => void;
  remove: (id: string) => void;
  setActive: (id: string | null) => void;
  /** Grava/substitui o snapshot de uma conversa (chamado após /enrich e após /query). */
  setSnapshot: (id: string, snapshot: ConversationSnapshot) => void;
}

const Ctx = createContext<ConversationsCtx | null>(null);

export function ConversationsProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  // Carrega do localStorage uma vez (client-only).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setConversations(JSON.parse(raw));
    } catch {
      /* storage indisponível — segue vazio */
    }
    setHydrated(true);
  }, []);

  // Persiste a cada mudança (só depois de hidratar, p/ não sobrescrever com []).
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch {
      /* ignora */
    }
  }, [conversations, hydrated]);

  const create = useCallback((title: string) => {
    const id = crypto.randomUUID();
    const conv: Conversation = {
      id,
      title: title.trim() || "Nova pesquisa",
      createdAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(id);
    return id;
  }, []);

  const rename = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: title.trim() || c.title } : c))
    );
  }, []);

  const remove = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setActiveId((prev) => (prev === id ? null : prev));
  }, []);

  const setSnapshot = useCallback((id: string, snapshot: ConversationSnapshot) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, snapshot } : c)));
  }, []);

  return (
    <Ctx.Provider
      value={{ conversations, activeId, create, rename, remove, setActive: setActiveId, setSnapshot }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useConversations() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConversations precisa de <ConversationsProvider>.");
  return ctx;
}

/** Agrupa as conversas por recência (Hoje / Ontem / Esta semana / Mais antigas). */
export function groupByRecency(convs: Conversation[]) {
  const startOfDay = (ms: number) => {
    const d = new Date(ms);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  };
  const today = startOfDay(Date.now());
  const yesterday = today - 86_400_000;
  const weekAgo = today - 7 * 86_400_000;

  const buckets: Record<string, Conversation[]> = { hoje: [], ontem: [], semana: [], antigas: [] };
  for (const c of [...convs].sort((a, b) => b.createdAt - a.createdAt)) {
    const day = startOfDay(c.createdAt);
    if (day === today) buckets.hoje.push(c);
    else if (day === yesterday) buckets.ontem.push(c);
    else if (day > weekAgo) buckets.semana.push(c);
    else buckets.antigas.push(c);
  }

  const out: { label: string; items: Conversation[] }[] = [];
  if (buckets.hoje.length) out.push({ label: "Hoje", items: buckets.hoje });
  if (buckets.ontem.length) out.push({ label: "Ontem", items: buckets.ontem });
  if (buckets.semana.length) out.push({ label: "Esta semana", items: buckets.semana });
  if (buckets.antigas.length) out.push({ label: "Mais antigas", items: buckets.antigas });
  return out;
}
