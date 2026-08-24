"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { StepIndicator } from "@/components/step-indicator";
import { PageTopbar } from "@/components/ui/page-topbar";
import {
  X,
  Plus,
  ArrowRight,
  Sparkles,
  FileText,
  Check,
  Pencil,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";

interface EntitySchema {
  pedido_principal: string;
  agente_nocivo: string[];
  violacoes: string[];
  normas: string[];
  empresa_ciente: boolean | null;
  setor: string | null;
  cargo: string | null;
  tese_central: string;
}

const initialData: EntitySchema = {
  pedido_principal: "Adicional de insalubridade grau máximo",
  agente_nocivo: ["Benzeno", "Hidrocarbonetos aromáticos"],
  violacoes: [
    "Ausência de EPI eficaz",
    "Falta de treinamento",
    "Exposição contínua sem monitoramento",
  ],
  normas: ["NR-15", "CLT art. 192", "Súmula 448 TST"],
  empresa_ciente: true,
  setor: "Indústria química",
  cargo: "Operador de caldeira",
  tese_central:
    "A empresa tinha ciência do risco e não forneceu proteção adequada, expondo o trabalhador a agentes cancerígenos de forma contínua e sem qualquer monitoramento de saúde ocupacional.",
};

interface ColorScheme {
  bg: string;
  border: string;
  text: string;
  dot: string;
  addBorder: string;
  addHover: string;
}

const colors: Record<"blue" | "green" | "amber", ColorScheme> = {
  blue: {
    bg: "bg-[#EEF3FB] dark:bg-[#1A2A3C]",
    border: "border-[#C8D9EF] dark:border-[#2A3A4C]",
    text: "text-[#1A3A5C] dark:text-[#8AB0DC]",
    dot: "bg-[#1A3A5C] dark:bg-[#8AB0DC]",
    addBorder: "border-[#C8D0DC] dark:border-[#33333C]",
    addHover:
      "hover:border-[#1A3A5C] dark:hover:border-[#8AB0DC] hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] hover:bg-[#EEF3FB] dark:hover:bg-[#1A2A3C]",
  },
  green: {
    bg: "bg-[#EDF7F2] dark:bg-[#122A1E]",
    border: "border-[#BDE0CF] dark:border-[#1E4A34]",
    text: "text-[#1A5C3A] dark:text-[#6FCB9A]",
    dot: "bg-[#2D8A5F] dark:bg-[#3DA372]",
    addBorder: "border-[#BDC8C4] dark:border-[#2A3A32]",
    addHover:
      "hover:border-[#2D8A5F] dark:hover:border-[#3DA372] hover:text-[#1A5C3A] dark:hover:text-[#6FCB9A] hover:bg-[#EDF7F2] dark:hover:bg-[#122A1E]",
  },
  amber: {
    bg: "bg-[#FBF4EC] dark:bg-[#2A2015]",
    border: "border-[#EDD9BC] dark:border-[#4A3A22]",
    text: "text-[#6B3B0A] dark:text-[#E0AC6C]",
    dot: "bg-[#C47A2D] dark:bg-[#C98A3D]",
    addBorder: "border-[#DCCAAC] dark:border-[#3A2E1E]",
    addHover:
      "hover:border-[#C47A2D] dark:hover:border-[#C98A3D] hover:text-[#6B3B0A] dark:hover:text-[#E0AC6C] hover:bg-[#FBF4EC] dark:hover:bg-[#2A2015]",
  },
};

function TagList({
  items,
  onChange,
  colorScheme,
  placeholder,
}: {
  items: string[];
  onChange: (next: string[]) => void;
  colorScheme: ColorScheme;
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
            className={`group flex items-center rounded-lg border transition-all ${colorScheme.bg} ${colorScheme.border}`}
            style={{
              opacity: isRemoving ? 0 : 1,
              transform: isRemoving ? "scale(0.9)" : "scale(1)",
              transition: "opacity 0.18s ease, transform 0.18s ease",
            }}
          >
            <div className={`w-1.5 h-1.5 rounded-full mx-2.5 flex-shrink-0 ${colorScheme.dot}`} />
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
                className={`bg-transparent outline-none py-1.5 pr-1 ${colorScheme.text}`}
                style={{ fontSize: "13.8px", fontWeight: 500, minWidth: "80px", maxWidth: "200px" }}
              />
            ) : (
              <span
                className={`py-1.5 cursor-default select-none ${colorScheme.text}`}
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
              <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity pr-1 ml-1 gap-0.5">
                <button
                  onClick={() => {
                    setEditIdx(idx);
                    setEditVal(item);
                  }}
                  className="flex items-center justify-center rounded hover:bg-black/8 dark:hover:bg-white/10 transition-colors"
                  style={{ width: "18px", height: "18px" }}
                >
                  <Pencil className={`opacity-55 ${colorScheme.text}`} style={{ width: "9px", height: "9px" }} strokeWidth={2} />
                </button>
                <button
                  onClick={() => remove(idx)}
                  className="flex items-center justify-center rounded hover:bg-black/8 dark:hover:bg-white/10 transition-colors"
                  style={{ width: "18px", height: "18px" }}
                >
                  <X className={`opacity-45 ${colorScheme.text}`} style={{ width: "9px", height: "9px" }} strokeWidth={2.5} />
                </button>
              </div>
            )}
          </div>
        );
      })}

      {adding ? (
        <div className={`flex items-center rounded-lg border px-2.5 py-1.5 ${colorScheme.bg} ${colorScheme.border}`} style={{ minWidth: "110px" }}>
          <div className={`w-1.5 h-1.5 rounded-full mr-2 flex-shrink-0 ${colorScheme.dot}`} />
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
            className={`bg-transparent outline-none ${colorScheme.text}`}
            style={{ fontSize: "13.8px", fontWeight: 500, width: "110px" }}
          />
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className={`flex items-center gap-1 rounded-lg border border-dashed px-2.5 py-1.5 transition-all text-[#9090A8] dark:text-[#7C7C88] ${colorScheme.addBorder} ${colorScheme.addHover}`}
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

function BooleanToggle({ value, onChange }: { value: boolean | null; onChange: (v: boolean | null) => void }) {
  const options: {
    label: string;
    val: boolean | null;
    active: string;
    icon: React.ReactNode;
  }[] = [
    {
      label: "Sim",
      val: true,
      active: "bg-[#EDF7F2] dark:bg-[#122A1E] border-[#BDE0CF] dark:border-[#1E4A34] text-[#1A5C3A] dark:text-[#6FCB9A]",
      icon: <Check style={{ width: "10px", height: "10px" }} strokeWidth={2.5} />,
    },
    {
      label: "Não",
      val: false,
      active: "bg-[#FBF0F0] dark:bg-[#2A1517] border-[#E8C2C2] dark:border-[#4A2529] text-[#7A1A1A] dark:text-[#E08A93]",
      icon: <X style={{ width: "10px", height: "10px" }} strokeWidth={2.5} />,
    },
    {
      label: "Não identificado",
      val: null,
      active: "bg-[#F5F5F8] dark:bg-[#1C1C21] border-[#DCDCE8] dark:border-[#2A2A32] text-[#6A6A7A] dark:text-[#9494A2]",
      icon: <HelpCircle style={{ width: "10px", height: "10px" }} strokeWidth={2} />,
    },
  ];

  return (
    <div className="flex gap-1.5 flex-wrap">
      {options.map((opt) => {
        const active = value === opt.val;
        return (
          <button
            key={String(opt.val)}
            onClick={() => onChange(opt.val)}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 transition-all ${
              active ? opt.active : "border-[#DCDCE8] dark:border-[#2A2A32] text-[#9090A8] dark:text-[#7C7C88]"
            }`}
            style={{ fontWeight: active ? 600 : 400, fontSize: "13.8px" }}
          >
            {opt.icon}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function FieldCard({ children }: { children: React.ReactNode }) {
  return <div className="p-4 rounded-xl border border-[#E8E8F0] dark:border-[#26262C] bg-[#FAFBFF] dark:bg-[#15191F]">{children}</div>;
}

function FieldLabel({ label, description }: { label: string; description?: string }) {
  return (
    <div className="mb-2">
      <span className="text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
        {label}
      </span>
      {description && (
        <span className="ml-2 text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "11.5px" }}>
          {description}
        </span>
      )}
    </div>
  );
}

/** Revisão de entidades extraídas (Figura 3 da RFC). Dados mockados até a extração real existir. */
export function EntityReviewPage() {
  const router = useRouter();
  const [data, setData] = useState<EntitySchema>(initialData);
  const [teseFocused, setTeseFocused] = useState(false);
  const wordCount = data.tese_central.trim().split(/\s+/).filter(Boolean).length;

  const set = <K extends keyof EntitySchema>(key: K) => (val: EntitySchema[K]) =>
    setData((prev) => ({ ...prev, [key]: val }));

  return (
    <main className="flex-1 flex flex-col h-full overflow-y-auto bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <PageTopbar
        hideFirstOnMobile
        queriesLeft={47}
        crumbs={[{ label: "Início", onClick: () => router.push("/") }, { label: "Revisão de contexto" }]}
      />

      {/* Body */}
      <div className="flex-1 flex flex-col items-center px-4 sm:px-8 py-4 pb-10">
        <StepIndicator current={1} />

        {/* Main card */}
        <div className="w-full max-w-[800px] bg-white dark:bg-[#17171B] rounded-2xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_4px_32px_rgba(0,0,0,0.07)] dark:shadow-none overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 px-5 sm:px-7 pt-6 pb-5 border-b border-[#F0F0F6] dark:border-[#26262C]">
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-[#EFF4FA] dark:bg-[#1A2A3C] flex-shrink-0 mt-0.5">
                <Sparkles style={{ width: "17px", height: "17px" }} className="text-[#1A3A5C] dark:text-[#8AB0DC]" strokeWidth={1.8} />
              </div>
              <div>
                <h2 className="text-[#0F1117] dark:text-[#ECECEF] tracking-[-0.015em]" style={{ fontSize: "17.8px", fontWeight: 600 }}>
                  Contexto jurídico identificado
                </h2>
                <p className="text-[#8A8A9A] dark:text-[#9494A2] mt-0.5" style={{ fontSize: "14.4px" }}>
                  Revise cada campo antes de prosseguir. Duplo clique em qualquer tag para editar.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#EDF7F2] dark:bg-[#122A1E] border border-[#BDE0CF] dark:border-[#1E4A34]">
                <div className="w-1.5 h-1.5 rounded-full bg-[#2D8A5F] dark:bg-[#3DA372]" />
                <span className="text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "12.1px", fontWeight: 600 }}>
                  Confiança: Alta
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 px-5 sm:px-7 py-2.5 bg-[#FAFAFA] dark:bg-[#1C1C21] border-b border-[#F0F0F6] dark:border-[#26262C] overflow-hidden">
            <FileText className="w-3.5 h-3.5 text-[#AEAEBF] dark:text-[#6E6E7C]" strokeWidth={1.8} />
            <span className="text-[#7A7A8E] dark:text-[#9E9EAC]" style={{ fontSize: "13.8px" }}>
              Extraído de:
            </span>
            <span className="text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.8px", fontWeight: 500 }}>
              Petição_Insalubridade_Benzeno_v2.pdf
            </span>
          </div>

          <div className="px-5 sm:px-7 pt-6 pb-5 space-y-6">
            <FieldCard>
              <FieldLabel label="Pedido principal" description="O que se pede na ação" />
              <InlineEdit value={data.pedido_principal} onChange={(v) => set("pedido_principal")(v ?? "")} placeholder="Ex: adicional de insalubridade grau máximo" />
            </FieldCard>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldCard>
                <FieldLabel label="Agentes nocivos" description="Agentes de risco identificados" />
                <TagList items={data.agente_nocivo} onChange={set("agente_nocivo")} colorScheme={colors.amber} placeholder="Novo agente…" />
              </FieldCard>
              <FieldCard>
                <FieldLabel label="Normas jurídicas" description="Normas e dispositivos citados" />
                <TagList items={data.normas} onChange={set("normas")} colorScheme={colors.blue} placeholder="Ex: NR-15…" />
              </FieldCard>
            </div>

            <FieldCard>
              <FieldLabel label="Violações identificadas" description="Condutas omissivas ou comissivas do empregador" />
              <TagList items={data.violacoes} onChange={set("violacoes")} colorScheme={colors.green} placeholder="Nova violação…" />
            </FieldCard>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <FieldCard>
                <FieldLabel label="Setor / Ramo" description="Ramo de atividade" />
                <InlineEdit value={data.setor} onChange={set("setor")} placeholder="Ex: metalurgia" />
              </FieldCard>
              <FieldCard>
                <FieldLabel label="Cargo" description="Cargo do trabalhador" />
                <InlineEdit value={data.cargo} onChange={set("cargo")} placeholder="Ex: operador de prensa" />
              </FieldCard>
              <FieldCard>
                <FieldLabel label="Ciência patronal" description="Evidência de conhecimento do risco" />
                <BooleanToggle value={data.empresa_ciente} onChange={set("empresa_ciente")} />
              </FieldCard>
            </div>

            <div>
              <FieldLabel label="Tese central" description="Frase que resume o argumento principal" />
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

        {/* Footer actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 w-full max-w-[800px] mt-5">
          <button onClick={() => router.push("/")} className="text-[#9090A8] dark:text-[#7C7C88] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE] transition-colors self-start" style={{ fontSize: "14.9px" }}>
            ← Voltar
          </button>

          <div className="flex items-center justify-between sm:justify-end gap-4">
            <span className="text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "13.8px" }}>
              {data.agente_nocivo.length + data.violacoes.length + data.normas.length} entidades confirmadas
            </span>
            <button
              onClick={() => router.push("/resultados")}
              className="flex items-center gap-2.5 px-6 py-2.5 rounded-xl bg-[#1A3A5C] text-white hover:bg-[#152E4A] active:scale-[0.98] transition-all shadow-[0_2px_14px_rgba(26,58,92,0.30)]"
              style={{ fontSize: "15.5px", fontWeight: 600 }}
            >
              Buscar jurisprudências
              <ArrowRight className="w-4 h-4" strokeWidth={2} />
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
