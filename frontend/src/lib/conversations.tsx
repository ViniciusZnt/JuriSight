"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ConversaApi, EstruturaArgumentativa, NovaVersaoBody, ResultCard, VersaoApi } from "@/lib/api";
import { adicionarVersaoConversa, apagarConversa, criarConversa, listarConversas, renomearConversa } from "@/lib/api";

/** Uma versão de busca dentro de uma conversa — o que vira "V{numero}" no dropdown de
 *  versões da página de Resultados. Cada "Refinar consulta" bem-sucedido cria uma versão
 *  nova; nenhuma sobrescreve as anteriores. Persistido no Postgres
 *  (query/api/conversa_routes.py), escopado ao usuário da sessão — nunca o PDF enviado
 *  nem seu texto, só a EstruturaArgumentativa revisada e os resultados do /query (ver
 *  conversations/db.py no backend para o porquê). */
export interface ConversationVersion {
  numero: number;
  estrutura: EstruturaArgumentativa;
  hasFile: boolean;
  fileName: string | null;
  pdfExtraido: boolean | null;
  aviso: string | null;
  resultados: ResultCard[] | null;
  createdAt: number; // epoch ms
}

/** O conteúdo de uma versão, sem o número (a API atribui o número — ver
 *  ConversationsCtx.addVersion) nem o timestamp (o backend que grava). */
export type ConversationSnapshot = Omit<ConversationVersion, "numero" | "createdAt">;

/** Uma pesquisa salva (o "histórico" da sidebar) — pode ter várias versões. */
export interface Conversation {
  id: string;
  title: string;
  createdAt: number; // epoch ms
  versions: ConversationVersion[];
}

function versionFromApi(v: VersaoApi): ConversationVersion {
  return {
    numero: v.numero,
    estrutura: v.estrutura,
    hasFile: v.has_file,
    fileName: v.file_name,
    pdfExtraido: v.pdf_extraido,
    aviso: v.aviso,
    resultados: v.resultados,
    createdAt: new Date(v.criado_em).getTime(),
  };
}

function fromApi(c: ConversaApi): Conversation {
  return {
    id: c.id,
    title: c.titulo,
    createdAt: new Date(c.criado_em).getTime(),
    versions: c.versoes.map(versionFromApi),
  };
}

interface ConversationsCtx {
  conversations: Conversation[];
  activeId: string | null;
  /** true enquanto a lista inicial ainda está carregando da API. */
  loading: boolean;
  create: (title: string) => Promise<string>; // resolve com o id novo
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  setActive: (id: string | null) => void;
  /** Acrescenta uma versão nova à conversa (nunca sobrescreve as anteriores) — chamado
   *  toda vez que POST /query retorna com sucesso. Devolve a versão recém-criada (já com
   *  o número atribuído pelo backend), pra quem chamou saber qual exibir. */
  addVersion: (id: string, snapshot: ConversationSnapshot) => Promise<ConversationVersion>;
}

const Ctx = createContext<ConversationsCtx | null>(null);

export function ConversationsProvider({ children }: { children: React.ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Carrega do backend uma vez, ao montar (já dentro de <RequireAuth>, então a sessão já
  // está confirmada). Falha de rede aqui não derruba o app — só fica com histórico vazio.
  useEffect(() => {
    let cancelled = false;
    listarConversas()
      .then((lista) => {
        if (!cancelled) setConversations(lista.map(fromApi));
      })
      .catch((err) => {
        console.error("Falha ao carregar conversas:", err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const create = useCallback(async (title: string) => {
    const criada = await criarConversa(title.trim() || "Nova pesquisa");
    const conv = fromApi(criada);
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  }, []);

  const rename = useCallback(async (id: string, title: string) => {
    const atualizada = await renomearConversa(id, title.trim() || "Nova pesquisa");
    setConversations((prev) => prev.map((c) => (c.id === id ? fromApi(atualizada) : c)));
  }, []);

  const remove = useCallback(async (id: string) => {
    await apagarConversa(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setActiveId((prev) => (prev === id ? null : prev));
  }, []);

  const addVersion = useCallback(async (id: string, snapshot: ConversationSnapshot) => {
    const body: NovaVersaoBody = {
      estrutura: snapshot.estrutura,
      has_file: snapshot.hasFile,
      file_name: snapshot.fileName,
      pdf_extraido: snapshot.pdfExtraido,
      aviso: snapshot.aviso,
      resultados: snapshot.resultados,
    };
    const atualizada = await adicionarVersaoConversa(id, body);
    const conv = fromApi(atualizada);
    setConversations((prev) => prev.map((c) => (c.id === id ? conv : c)));
    return conv.versions[conv.versions.length - 1];
  }, []);

  return (
    <Ctx.Provider
      value={{ conversations, activeId, loading, create, rename, remove, setActive: setActiveId, addVersion }}
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
