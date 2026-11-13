"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { StepIndicator } from "@/components/step-indicator";
import { PageTopbar } from "@/components/ui/page-topbar";
import {
  X,
  Plus,
  ArrowRight,
  Sparkles,
  FileText,
  Pencil,
  AlertTriangle,
  PencilLine,
  Loader2,
} from "lucide-react";
import { FiltroRestrito } from "@/components/revisao/filtro-restrito";
import { useSearchSession } from "@/lib/search-session";
import { useConversations } from "@/lib/conversations";
import { emptyEstrutura, queryJurisprudencia, ApiError, type EstruturaArgumentativa } from "@/lib/api";
import { EtiquetaBusca } from "@/components/ui/etiqueta-busca";
import { BUSCA, TAG_TERMOS, type Busca } from "@/lib/cores-busca";

function TagList({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [adding, setAdding] = useState(false);
  const [newVal, setNewVal] = useState("");
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [editVal, setEditVal] = useState("");
  const [removingIdx, setRemovingIdx] = useState<number | null>(null);

  const newRef = useRef<HTMLInputElement>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (adding) newRef.current?.focus();
  }, [adding]);
  useEffect(() => {
    if (editIdx !== null) editRef.current?.focus();
  }, [editIdx]);

  const remove = (idx: number) => {
    setRemovingIdx(idx);
    setTimeout(() => {
      onChange(items.filter((_, i) => i !== idx));
      setRemovingIdx(null);
    }, 200);
  };

  const confirmAdd = () => {
    if (newVal.trim()) onChange([...items, newVal.trim()]);
    setNewVal("");
    setAdding(false);
  };

  const confirmEdit = (idx: number) => {
    if (editVal.trim()) {
      const next = [...items];
      next[idx] = editVal.trim();
      onChange(next);
    }
    setEditIdx(null);
    setEditVal("");
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, idx) => {
        const isRemoving = removingIdx === idx;
        const isEditing = editIdx === idx;
        return (
          <div
            key={idx}
            className={`group flex items-center rounded-lg border transition-all ${TAG_TERMOS.fundo}`}
            style={{
              opacity: isRemoving ? 0 : 1,
              transform: isRemoving ? "scale(0.9)" : "scale(1)",
              transition: "opacity 0.18s ease, transform 0.18s ease",
            }}
          >
            <div className={`w-1.5 h-1.5 rounded-full mx-2.5 flex-shrink-0 ${BUSCA.termos.ponto}`} />
            {isEditing ? (
              <input
                ref={editRef}
                value={editVal}
                onChange={(e) => setEditVal(e.target.value)}
                onBlur={() => confirmEdit(idx)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") confirmEdit(idx);
                  if (e.key === "Escape") {
                    setEditIdx(null);
                    setEditVal("");
                  }
                }}
                className={`bg-transparent outline-none py-1.5 pr-1 ${TAG_TERMOS.texto}`}
                style={{ fontSize: "13.8px", fontWeight: 500, minWidth: "80px", maxWidth: "200px" }}
              />
            ) : (
              <span
                className={`py-1.5 cursor-default select-none ${TAG_TERMOS.texto}`}
                style={{ fontSize: "13.8px", fontWeight: 500 }}
                onDoubleClick={() => {
                  setEditIdx(idx);
                  setEditVal(item);
                }}
              >
                {item}
              </span>
            )}
            {!isEditing && (
              <div className="flex items-center pr-1 ml-1 gap-0.5">
                <button
                  aria-label={`Editar ${item}`}
                  onClick={() => {
                    setEditIdx(idx);
                    setEditVal(item);
                  }}
                  className="flex items-center justify-center rounded hover:bg-black/8 dark:hover:bg-white/10 transition-colors"
                  style={{ width: "18px", height: "18px" }}
                >
                  <Pencil className={`opacity-55 ${TAG_TERMOS.texto}`} style={{ width: "9px", height: "9px" }} strokeWidth={2} />
                </button>
                <button
                  aria-label={`Remover ${item}`}
                  onClick={() => remove(idx)}
                  className="flex items-center justify-center rounded hover:bg-black/8 dark:hover:bg-white/10 transition-colors"
                  style={{ width: "18px", height: "18px" }}
                >
                  <X className={`opacity-45 ${TAG_TERMOS.texto}`} style={{ width: "9px", height: "9px" }} strokeWidth={2.5} />
                </button>
              </div>
            )}
          </div>
        );
      })}

      {adding ? (
        <div className={`flex items-center rounded-lg border px-2.5 py-1.5 ${TAG_TERMOS.fundo}`} style={{ minWidth: "110px" }}>
          <div className={`w-1.5 h-1.5 rounded-full mr-2 flex-shrink-0 ${BUSCA.termos.ponto}`} />
          <input
            ref={newRef}
            value={newVal}
            onChange={(e) => setNewVal(e.target.value)}
            onBlur={confirmAdd}
            onKeyDown={(e) => {
              if (e.key === "Enter") confirmAdd();
              if (e.key === "Escape") {
                setAdding(false);
                setNewVal("");
              }
            }}
            placeholder={placeholder}
            className={`bg-transparent outline-none ${TAG_TERMOS.texto}`}
            style={{ fontSize: "13.8px", fontWeight: 500, width: "110px" }}
          />
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className={`flex items-center gap-1 rounded-lg border border-dashed px-2.5 py-1.5 transition-all text-[#9090A8] dark:text-[#7C7C88] ${TAG_TERMOS.adicionar}`}
          style={{ fontSize: "13.8px" }}
        >
          <Plus style={{ width: "10px", height: "10px" }} strokeWidth={2.5} />
          Adicionar
        </button>
      )}
    </div>
  );
}

function InlineEdit({
  value,
  onChange,
  placeholder,
  emptyLabel = "Não identificado",
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  placeholder: string;
  emptyLabel?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const confirm = () => {
    onChange(draft.trim() || null);
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={confirm}
        onKeyDown={(e) => {
          if (e.key === "Enter") confirm();
          if (e.key === "Escape") {
            setEditing(false);
            setDraft(value ?? "");
          }
        }}
        placeholder={placeholder}
        className="w-full bg-transparent outline-none border-b border-[#1A3A5C]/30 dark:border-[#8AB0DC]/30 text-[#0F1117] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54]"
        style={{ fontSize: "14.9px", fontWeight: 500, paddingBottom: "2px" }}
      />
    );
  }

  return (
    <button onClick={() => { setDraft(value ?? ""); setEditing(true); }} className="group flex items-center gap-1.5 text-left w-full">
      <span
        className={value ? "text-[#0F1117] dark:text-[#ECECEF]" : "text-[#C0C0CE] dark:text-[#5E5E6A] italic"}
        style={{ fontSize: "14.9px", fontWeight: value ? 500 : 400 }}
      >
        {value ?? emptyLabel}
      </span>
      <Pencil
        className="opacity-0 group-hover:opacity-40 transition-opacity text-[#1A3A5C] dark:text-[#8AB0DC] flex-shrink-0"
        style={{ width: "11px", height: "11px" }}
        strokeWidth={2}
      />
    </button>
  );
}

function FieldCard({ children }: { children: React.ReactNode }) {
  return <div className="p-4 rounded-xl border border-[#E8E8F0] dark:border-[#26262C] bg-[#FAFBFF] dark:bg-[#15191F]">{children}</div>;
}

function FieldLabel({ label, description, busca }: { label: string; description?: string; busca?: Busca }) {
  return (
    <div className="mb-2">
      <span className="text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
        {label}
      </span>
      {busca && <span className="ml-2"><EtiquetaBusca busca={busca} /></span>}
      {description && (
        <span className="ml-2 text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "11.5px" }}>
          {description}
        </span>
      )}
    </div>
  );
}

/** Revisão de entidades extraídas (Figura 3 da RFC). A EstruturaArgumentativa vem de POST
 *  /enrich (via SearchSession, setado na Home); "Buscar jurisprudências" chama POST /query com a
 *  versão editada pelo usuário (RN05: revisão humana antes da busca). */
export function EntityReviewPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const manualParam = searchParams.get("modo") === "manual";
  const { estrutura: sessionEstrutura, hasFile, fileName, pdfExtraido, aviso, dispositivosIa, expressoesSugeridas, dispositivosSugeridos, setEstrutura: persistEstrutura, loadVersion } = useSearchSession();
  const { activeId, addVersion } = useConversations();

  // Sem estrutura na sessão (ex.: acesso direto à URL) cai no mesmo modo manual do UC02.
  const manual = manualParam || sessionEstrutura === null;
  const [data, setData] = useState<EstruturaArgumentativa>(() => sessionEstrutura ?? emptyEstrutura());
  const [teseFocused, setTeseFocused] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wordCount = data.tese_central.trim().split(/\s+/).filter(Boolean).length;

  const set = <K extends keyof EstruturaArgumentativa>(key: K) => (val: EstruturaArgumentativa[K]) =>
    setData((prev) => ({ ...prev, [key]: val }));

  const entidadesConfirmadas = data.agente_nocivo.length + data.violacoes.length + data.normas.length + data.dispositivos.length + data.expressoes.length;

  const buscar = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const resultados = await queryJurisprudencia({ estrutura: data });
      persistEstrutura(data);
      const snapshot = { estrutura: data, hasFile, fileName, pdfExtraido, aviso, resultados };
      // Cada busca bem-sucedida vira uma versão NOVA (V1 na 1ª vez, V2 ao "Refinar
      // consulta" e buscar de novo, ...) — nunca sobrescreve a anterior, é o que dá o
      // histórico navegável no dropdown de versões da página de Resultados.
      const versao = activeId
        ? await addVersion(activeId, snapshot)
        : { numero: 1, ...snapshot, createdAt: Date.now() }; // acesso direto à URL, sem conversa — só exibe, não persiste
      loadVersion(versao);
      router.push("/resultados");
    } catch (err) {
      console.error("Falha em /query:", err);
      setError(
        err instanceof ApiError
          ? err.message
          : "Não foi possível buscar jurisprudências agora. Tente novamente."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <PageTopbar
        hideFirstOnMobile
        crumbs={[{ label: "Início", onClick: () => router.push("/") }, { label: "Revisão de contexto" }]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-4 sm:px-8 py-4 pb-10">
        <StepIndicator current={1} manual={manual} />

        {/* Main card */}
        <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 px-5 sm:px-7 pt-6 pb-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex-shrink-0 mt-0.5">
                <Sparkles style={{ width: "17px", height: "17px" }} className="text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
              </div>
              <div>
                <h2 className="text-[#0F1117] dark:text-[#ECECEF] tracking-[-0.015em]" style={{ fontSize: "17.8px", fontWeight: 600 }}>
                  {manual ? "Complete o contexto jurídico" : "Contexto jurídico identificado"}
                </h2>
                <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-0.5" style={{ fontSize: "14.4px" }}>
                  {manual
                    ? "Preencha os campos abaixo com base no seu caso. Duplo clique em qualquer tag para editar."
                    : "Revise cada campo antes de prosseguir. Duplo clique em qualquer tag para editar."}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {manual ? (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#F5F5F8] dark:bg-[#1C1C21] border border-[#DCDCE8] dark:border-[#2A2A32]">
                  <PencilLine className="w-3 h-3 text-[#6A6A7A] dark:text-[#9494A2]" strokeWidth={1.8} />
                  <span className="text-[#6A6A7A] dark:text-[#9494A2]" style={{ fontSize: "12.1px", fontWeight: 600 }}>
                    Preenchimento manual
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#EDF7F2] dark:bg-[#122A1E] border border-[#BDE0CF] dark:border-[#1E4A34]">
                  <Sparkles className="w-3 h-3 text-[#1A5C3A] dark:text-[#6FCB9A]" strokeWidth={1.8} />
                  <span className="text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "12.1px", fontWeight: 600 }}>
                    Extraído via IA
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 px-5 sm:px-7 py-2.5 bg-[#FAFAFA] dark:bg-[#1C1C21] border-b border-[#F0F0F6] dark:border-[#26262C]">
            {manual ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-[#AEAEBF] dark:text-[#6E6E7C] flex-shrink-0" strokeWidth={1.8} />
                <span className="text-[#7A7A8E] dark:text-[#9E9EAC] min-w-0" style={{ fontSize: "13.8px" }}>
                  Busca sem contexto de documento — para resultados mais precisos, envie o PDF do caso.
                </span>
              </>
            ) : hasFile && fileName ? (
              <>
                <FileText className="w-3.5 h-3.5 text-[#AEAEBF] dark:text-[#6E6E7C] flex-shrink-0" strokeWidth={1.8} />
                <span className="text-[#7A7A8E] dark:text-[#9E9EAC] flex-shrink-0" style={{ fontSize: "13.8px" }}>
                  Extraído de:
                </span>
                <span className="text-[#4A4A5A] dark:text-[#C4C4CE] truncate min-w-0" style={{ fontSize: "13.8px", fontWeight: 500 }}>
                  {fileName}
                </span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-[#AEAEBF] dark:text-[#6E6E7C] flex-shrink-0" strokeWidth={1.8} />
                <span className="text-[#7A7A8E] dark:text-[#9E9EAC] min-w-0" style={{ fontSize: "13.8px" }}>
                  Extraído da intenção argumentativa descrita
                </span>
              </>
            )}
          </div>

          <div className="px-5 sm:px-7 pt-6 pb-5 space-y-6">
            <FieldCard>
              <FieldLabel label="Pedido principal" busca="termos" description="O que se pede na ação" />
              <InlineEdit value={data.pedido_principal} onChange={(v) => set("pedido_principal")(v ?? "")} placeholder="Ex: adicional de insalubridade grau máximo" />
            </FieldCard>

            <FiltroRestrito
              dispositivos={data.dispositivos}
              expressoes={data.expressoes}
              normas={data.normas}
              tribunais={data.tribunais}
              fase={data.fase}
              dispositivosIa={dispositivosIa}
              expressoesSugeridas={expressoesSugeridas}
              dispositivosSugeridos={dispositivosSugeridos}
              onChange={(patch) => setData((prev) => ({ ...prev, ...patch }))}
            />

            <FieldCard>
                <FieldLabel label="Fatos do caso" busca="termos" description="Situações que caracterizam o caso (ex.: gravidez, ruído, jornada controlada)" />
                <TagList items={data.agente_nocivo} onChange={set("agente_nocivo")} placeholder="Novo fato…" />
            </FieldCard>

            <FieldCard>
              <FieldLabel label="Condutas da empresa" busca="termos" description="O que a empresa fez ou deixou de fazer" />
              <TagList items={data.violacoes} onChange={set("violacoes")} placeholder="Nova conduta…" />
            </FieldCard>


            <div>
              <FieldLabel label="Tese central" busca="semantica" description="Frase que resume o argumento principal" />
              <div
                className={`relative rounded-xl border transition-all bg-[#FAFAFA] dark:bg-[#1C1C21] ${
                  teseFocused
                    ? "border-[#1A3A5C] dark:border-[#8AB0DC] shadow-[0_0_0_3px_rgba(26,58,92,0.07)] dark:shadow-[0_0_0_3px_rgba(138,176,220,0.1)]"
                    : "border-[#E4E4EC] dark:border-[#26262C]"
                }`}
              >
                <textarea
                  value={data.tese_central}
                  onChange={(e) => set("tese_central")(e.target.value)}
                  onFocus={() => setTeseFocused(true)}
                  onBlur={() => setTeseFocused(false)}
                  rows={3}
                  placeholder="Ex: A empresa tinha ciência do risco e não forneceu proteção adequada…"
                  className="w-full bg-transparent outline-none resize-none px-4 pt-4 pb-10 text-[#1A1A2A] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] leading-relaxed"
                  style={{ fontSize: "15.5px" }}
                />
                <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-4 py-2 border-t border-[#EBEBF2] dark:border-[#26262C]">
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle className="w-3 h-3 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
                    <span className="text-[#C0C0CE] dark:text-[#5E5E6A]" style={{ fontSize: "12.6px" }}>
                      A IA priorizará decisões alinhadas a esta tese
                    </span>
                  </div>
                  <span className="text-[#C0C0D0] dark:text-[#5E5E6A]" style={{ fontSize: "12.6px" }}>
                    {wordCount} {wordCount === 1 ? "palavra" : "palavras"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {submitting && (
          <div className="w-full max-w-[800px] mt-4 flex items-start gap-2.5 rounded-xl border border-[#D0DEEE] dark:border-[#2A3A4C] bg-[#EFF4FA] dark:bg-[#1A2A3C] px-4 py-3">
            <Loader2 className="w-4 h-4 text-[#1A3A5C] dark:text-[#8AB0DC] mt-0.5 flex-shrink-0 animate-spin" strokeWidth={1.8} />
            <p className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.8px" }}>
              Buscando jurisprudências na base (~470 mil trechos indexados)… Pode levar alguns
              minutos, principalmente com a máquina sob carga. Não recarregue a página.
            </p>
          </div>
        )}

        {error && (
          <div className="w-full max-w-[800px] mt-4 flex items-start gap-2.5 rounded-xl border border-[#E8C2C2] dark:border-[#4A2529] bg-[#FBF0F0] dark:bg-[#2A1517] px-4 py-3">
            <AlertTriangle className="w-4 h-4 text-[#C44040] dark:text-[#D96B6B] mt-0.5 flex-shrink-0" strokeWidth={1.8} />
            <p className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.8px" }}>{error}</p>
          </div>
        )}

        {/* Footer actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 w-full max-w-[800px] mt-5">
          <button onClick={() => router.push("/")} className="text-[#9090A8] dark:text-[#7C7C88] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors self-start" style={{ fontSize: "14.9px" }}>
            ← Voltar
          </button>

          <div className="flex items-center justify-between sm:justify-end gap-4">
            <span className="text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "13.8px" }}>
              {entidadesConfirmadas} entidades confirmadas
            </span>
            <button
              onClick={buscar}
              disabled={submitting}
              className="flex items-center gap-2.5 px-6 py-2.5 rounded-xl bg-[#1A3A5C] text-white hover:bg-[#152E4A] active:scale-[0.98] transition-all shadow-[0_2px_14px_rgba(26,58,92,0.30)] disabled:opacity-70 disabled:pointer-events-none"
              style={{ fontSize: "15.5px", fontWeight: 600 }}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2} />
                  Buscando…
                </>
              ) : (
                <>
                  Buscar jurisprudências
                  <ArrowRight className="w-4 h-4" strokeWidth={2} />
                </>
              )}
            </button>
          </div>
        </div>

        <p className="text-[#C8C8D4] dark:text-[#5E5E6A] mt-4" style={{ fontSize: "12.6px" }}>
          Duplo clique em uma tag para editar · Enter para confirmar · Esc para cancelar
        </p>
      </div>
    </main>
  );
}
