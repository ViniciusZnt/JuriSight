"use client";

import { useState } from "react";
import { Check, ChevronDown, ChevronUp, Gavel, PencilLine, Sparkles } from "lucide-react";
import {
  ApiError,
  enviarCorrecaoProvimento,
  type ClassificacaoProvimento,
  type CorrecaoProvimento,
  type Provimento,
} from "@/lib/api";
import {
  PERGUNTAS,
  PROVIMENTO_LABEL,
  nivelConfianca,
  probabilidadesOrdenadas,
  resumoProvimento,
  type NivelConfianca,
  type Pergunta,
} from "@/lib/provimento";

const NIVEL_CLASSES: Record<NivelConfianca, { texto: string; barra: string; label: string }> = {
  alta: { texto: "text-[#1A5C3A] dark:text-[#6FCB9A]", barra: "bg-[#2D8A5F] dark:bg-[#3DA372]", label: "alta" },
  media: { texto: "text-[#8A5A1E] dark:text-[#E0AC6C]", barra: "bg-[#C98A3A] dark:bg-[#E0AC6C]", label: "média" },
  baixa: { texto: "text-[#6A6A7A] dark:text-[#9494A2]", barra: "bg-[#9090A8] dark:bg-[#7C7C88]", label: "baixa" },
};

const pct = (p: number | null | undefined) => `${Math.round((p ?? 0) * 100)}%`;

function Barra({ valor, classe }: { valor: number; classe: string }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-[#EEEEF4] dark:bg-[#26262C] overflow-hidden">
      <div className={`h-full rounded-full ${classe}`} style={{ width: pct(valor) }} />
    </div>
  );
}

interface ProvimentoPanelProps {
  documentoId: string;
  provimento: Provimento;
  classificacao?: ClassificacaoProvimento | null;
  /** Card de resultado: só a faixa-resumo, com o painel completo atrás de um botão. */
  compacto?: boolean;
}

/** Provimento classificado pelo Jev (resultado, quem recorreu, a quem favorece), com as
 *  probabilidades de cada opção e o envio de correção pelo usuário. */
export function ProvimentoPanel({ documentoId, provimento, classificacao, compacto = false }: ProvimentoPanelProps) {
  const [aberto, setAberto] = useState(!compacto);
  const [probAberta, setProbAberta] = useState<Pergunta | null>(null);
  const [editando, setEditando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState<CorrecaoProvimento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [form, setForm] = useState<CorrecaoProvimento>(() => ({
    resultado: classificacao?.resultado ?? "nao_provido",
    recorrente: classificacao?.recorrente ?? "indefinido",
    favorece: classificacao?.favorece ?? "indefinido",
    comentario: "",
  }));

  if (!classificacao) {
    return (
      <div onClick={(e) => e.stopPropagation()} className="flex items-center gap-2 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
        <Gavel className="w-3.5 h-3.5" strokeWidth={1.8} />
        <span>
          Provimento: <span className="text-[#4A4A5A] dark:text-[#C4C4CE] font-medium">{PROVIMENTO_LABEL[provimento]}</span> · ainda não classificado pela IA
        </span>
      </div>
    );
  }

  const nivelResultado = NIVEL_CLASSES[nivelConfianca(classificacao.confianca_resultado)];

  const enviar = async (corpo: CorrecaoProvimento) => {
    setEnviando(true);
    setErro(null);
    try {
      await enviarCorrecaoProvimento(documentoId, corpo);
      setEnviado(corpo);
      setEditando(false);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível enviar a correção.");
    } finally {
      setEnviando(false);
    }
  };

  const selectClass =
    "w-full rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#1C1C21] text-[#4A4A5A] dark:text-[#C4C4CE] px-2 py-1.5 outline-none focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC]";

  return (
    <div onClick={(e) => e.stopPropagation()} className="cursor-default">
      {compacto && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-start gap-2 min-w-0 text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "13.2px" }}>
            <span className={`w-2 h-2 mt-1.5 rounded-full flex-shrink-0 ${nivelResultado.barra}`} title={`Confiança ${nivelResultado.label}`} />
            <span>{resumoProvimento(classificacao)}</span>
          </div>
          <button
            onClick={() => setAberto((v) => !v)}
            aria-expanded={aberto}
            className="flex items-center gap-1 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
            style={{ fontSize: "12.6px", fontWeight: 500 }}
          >
            Detalhes do provimento
            {aberto ? <ChevronUp className="w-3 h-3" strokeWidth={2} /> : <ChevronDown className="w-3 h-3" strokeWidth={2} />}
          </button>
        </div>
      )}

      {aberto && (
        <div className={`${compacto ? "mt-3 rounded-xl border border-[#E4E4EC] dark:border-[#26262C] bg-[#FAFAFC] dark:bg-[#1A1A1F] p-4" : ""} space-y-3`}>
          {PERGUNTAS.map(({ chave, titulo, labels }) => {
            const escolha = classificacao[chave];
            const conf = classificacao[`confianca_${chave}`];
            const nivel = NIVEL_CLASSES[nivelConfianca(conf)];
            const probs = probabilidadesOrdenadas(classificacao.probabilidades[chave]);
            return (
              <div key={chave} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[#8A8A9A] dark:text-[#9494A2] uppercase tracking-[0.05em]" style={{ fontSize: "11.5px", fontWeight: 600 }}>
                    {titulo}
                  </span>
                  <span className={nivel.texto} style={{ fontSize: "12.1px", fontWeight: 600 }}>
                    {pct(conf)} · confiança {nivel.label}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "14.4px", fontWeight: 600 }}>
                    {labels[escolha]}
                  </span>
                  {probs.length > 1 && (
                    <button
                      onClick={() => setProbAberta((p) => (p === chave ? null : chave))}
                      aria-expanded={probAberta === chave}
                      aria-label={`Ver probabilidades: ${titulo}`}
                      className="text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline flex-shrink-0"
                      style={{ fontSize: "12.1px" }}
                    >
                      {probAberta === chave ? "Ocultar" : "Ver probabilidades"}
                    </button>
                  )}
                </div>
                <Barra valor={conf ?? 0} classe={nivel.barra} />
                {probAberta === chave && (
                  <ul className="pt-1 space-y-1.5">
                    {probs.map(({ valor, prob }) => (
                      <li key={valor} className="grid grid-cols-[minmax(0,1fr)_3rem] items-center gap-x-3 gap-y-0.5">
                        <span className="text-[#4A4A5A] dark:text-[#C4C4CE] truncate" style={{ fontSize: "12.6px", fontWeight: valor === escolha ? 600 : 400 }}>
                          {labels[valor] ?? valor}
                        </span>
                        <span className="text-right tabular-nums text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.1px" }}>
                          {pct(prob)}
                        </span>
                        <div className="col-span-2">
                          <Barra valor={prob} classe={valor === escolha ? "bg-[#1A3A5C] dark:bg-[#8AB0DC]" : "bg-[#C8CCDA] dark:bg-[#3A3A44]"} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}

          <div className="pt-3 border-t border-[#F0F0F6] dark:border-[#26262C] space-y-3">
            <p className="flex items-center gap-1.5 text-[#AEAEBF] dark:text-[#6E6E7C]" style={{ fontSize: "12.1px" }}>
              <Sparkles className="w-3 h-3" strokeWidth={1.8} />
              Classificado pelo Jev ({classificacao.modelo}) · pode conter erros
            </p>

            {enviado && !editando ? (
              <p className="flex items-center gap-1.5 text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "13.2px", fontWeight: 500 }}>
                <Check className="w-3.5 h-3.5" strokeWidth={2.2} />
                Obrigado! Sua correção foi registrada.
              </p>
            ) : editando ? (
              <div className="space-y-2.5">
                {PERGUNTAS.map(({ chave, titulo, labels }) => (
                  <label key={chave} htmlFor={`correcao-${chave}-${documentoId}`} className="flex flex-col gap-1">
                    <span className="text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.1px" }}>{titulo}</span>
                    <select
                      id={`correcao-${chave}-${documentoId}`}
                      value={form[chave]}
                      onChange={(e) => setForm((f) => ({ ...f, [chave]: e.target.value }))}
                      className={selectClass}
                      style={{ fontSize: "13.2px" }}
                    >
                      {Object.entries(labels).map(([valor, label]) => (
                        <option key={valor} value={valor}>{label}</option>
                      ))}
                    </select>
                  </label>
                ))}
                <label htmlFor={`correcao-comentario-${documentoId}`} className="flex flex-col gap-1">
                  <span className="text-[#6B6B80] dark:text-[#A6A6B4]" style={{ fontSize: "12.1px" }}>Comentário (opcional)</span>
                  <textarea
                    id={`correcao-comentario-${documentoId}`}
                    value={form.comentario ?? ""}
                    maxLength={1000}
                    rows={2}
                    onChange={(e) => setForm((f) => ({ ...f, comentario: e.target.value }))}
                    placeholder="Ex.: o recurso foi provido em parte, só quanto aos honorários"
                    className={`${selectClass} resize-y`}
                    style={{ fontSize: "13.2px" }}
                  />
                </label>
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => setEditando(false)}
                    className="px-3 py-1.5 text-[#9090A8] dark:text-[#7C7C88] hover:text-[#4A4A5A] dark:hover:text-[#C4C4CE]"
                    style={{ fontSize: "12.6px" }}
                  >
                    Cancelar
                  </button>
                  <button
                    disabled={enviando}
                    onClick={() => enviar({ ...form, comentario: form.comentario?.trim() || null })}
                    className="rounded-lg bg-[#1A3A5C] text-white px-3 py-1.5 hover:bg-[#1E4570] disabled:opacity-60 transition-colors"
                    style={{ fontSize: "12.6px", fontWeight: 600 }}
                  >
                    {enviando ? "Enviando…" : "Enviar correção"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[#8A8A9A] dark:text-[#9494A2] mr-1" style={{ fontSize: "12.6px" }}>A classificação está certa?</span>
                <button
                  disabled={enviando}
                  onClick={() =>
                    enviar({ resultado: classificacao.resultado, recorrente: classificacao.recorrente, favorece: classificacao.favorece, comentario: null })
                  }
                  className="flex items-center gap-1 rounded-lg border border-[#BDE0CF] dark:border-[#1E4A34] bg-[#EDF7F2] dark:bg-[#122A1E] text-[#1A5C3A] dark:text-[#6FCB9A] px-2.5 py-1 disabled:opacity-60"
                  style={{ fontSize: "12.6px", fontWeight: 600 }}
                >
                  <Check className="w-3 h-3" strokeWidth={2.2} />
                  Está correto
                </button>
                <button
                  onClick={() => setEditando(true)}
                  className="flex items-center gap-1 rounded-lg border border-[#E0E0EA] dark:border-[#2A2A32] bg-white dark:bg-[#17171B] text-[#4A4A5A] dark:text-[#C4C4CE] px-2.5 py-1 hover:border-[#1A3A5C]/30 dark:hover:border-[#8AB0DC]/30"
                  style={{ fontSize: "12.6px", fontWeight: 500 }}
                >
                  <PencilLine className="w-3 h-3" strokeWidth={1.8} />
                  Sugerir correção
                </button>
              </div>
            )}
            {erro && (
              <p role="alert" className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "12.6px" }}>
                {erro}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
