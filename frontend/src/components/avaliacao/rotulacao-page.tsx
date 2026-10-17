"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import {
  ApiError,
  enviarRotulo,
  obterFilaAvaliacao,
  type FilaAvaliacao,
  type ParAvaliacao,
  type StanceAvaliacao,
} from "@/lib/api";

const RELEVANCIAS = [
  { valor: 0, tecla: "1", rotulo: "0 Nada a ver" },
  { valor: 1, tecla: "2", rotulo: "1 Tema vizinho" },
  { valor: 2, tecla: "3", rotulo: "2 Mesmo pedido" },
  { valor: 3, tecla: "4", rotulo: "3 Mesmo caso" },
];

const STANCES: { valor: StanceAvaliacao; tecla: string; rotulo: string }[] = [
  { valor: "fortalece", tecla: "f", rotulo: "Fortalece" },
  { valor: "enfraquece", tecla: "e", rotulo: "Enfraquece" },
  { valor: "neutro", tecla: "n", rotulo: "Neutro" },
];

type Estado =
  | { tipo: "carregando" }
  | { tipo: "restrito"; mensagem: string }
  | { tipo: "erro"; mensagem: string }
  | { tipo: "ok"; fila: FilaAvaliacao };

function mensagemDe(e: unknown): string {
  return e instanceof Error ? e.message : "Erro inesperado.";
}

/** Atalhos não valem digitando em campos de texto nem com modificadores (Ctrl+F etc.). */
function ignorarTecla(e: KeyboardEvent): boolean {
  if (e.ctrlKey || e.metaKey || e.altKey) return true;
  const alvo = e.target as HTMLElement | null;
  if (!alvo) return false;
  return alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.isContentEditable;
}

/** Avaliação — a especialista rotula um par (tese, acórdão) por vez: relevância 0-3 e stance.
 *  Ao escolher os dois eixos o rótulo é enviado sozinho e o próximo par é carregado. */
export function RotulacaoPage() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [relevancia, setRelevancia] = useState<number | null>(null);
  const [stance, setStance] = useState<StanceAvaliacao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  // Ref além do state: duas teclas no mesmo tick não podem disparar dois POSTs.
  const enviandoRef = useRef(false);

  const carregar = useCallback(async () => {
    setEstado({ tipo: "carregando" });
    try {
      setEstado({ tipo: "ok", fila: await obterFilaAvaliacao() });
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setEstado({ tipo: "restrito", mensagem: e.message });
      else setEstado({ tipo: "erro", mensagem: mensagemDe(e) });
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial da fila
    void carregar();
  }, [carregar]);

  const par: ParAvaliacao | null = estado.tipo === "ok" ? estado.fila.par : null;
  const parId = par?.id ?? null;

  // Envio automático quando os dois eixos estão escolhidos. Se falhar, a seleção fica para
  // a especialista tentar de novo (mudar uma escolha ou "Tentar de novo" reenvia).
  const enviar = useCallback(async () => {
    if (!parId || relevancia === null || stance === null || enviandoRef.current) return;
    enviandoRef.current = true;
    setEnviando(true);
    setErroEnvio(null);
    try {
      await enviarRotulo(parId, relevancia, stance);
      setRelevancia(null);
      setStance(null);
      enviandoRef.current = false;
      setEnviando(false);
      await carregar();
    } catch (e) {
      setErroEnvio(mensagemDe(e));
      enviandoRef.current = false;
      setEnviando(false);
    }
  }, [parId, relevancia, stance, carregar]);

  useEffect(() => {
    if (relevancia !== null && stance !== null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- dispara o POST ao completar os dois eixos
      void enviar();
    }
    // Só reage à mudança de escolha; `enviar` muda junto com elas.
  }, [relevancia, stance]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!parId) return;
    const onKey = (e: KeyboardEvent) => {
      if (ignorarTecla(e) || enviandoRef.current) return;
      const k = e.key.toLowerCase();
      const rel = RELEVANCIAS.find((r) => r.tecla === k);
      if (rel) {
        setRelevancia(rel.valor);
        return;
      }
      const st = STANCES.find((s) => s.tecla === k);
      if (st) setStance(st.valor);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [parId]);

  const escolherRelevancia = (v: number) => !enviandoRef.current && setRelevancia(v);
  const escolherStance = (v: StanceAvaliacao) => !enviandoRef.current && setStance(v);

  return (
    <div className="min-h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <header className="flex items-center justify-between gap-4 pl-20 pr-8 py-4">
        <h1 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "20.7px", fontWeight: 600 }}>
          Avaliação
        </h1>
        {estado.tipo === "ok" && estado.fila.par && (
          <span className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.4px", fontWeight: 500 }}>
            {estado.fila.feitos} de {estado.fila.total}
          </span>
        )}
      </header>

      <div className="px-4 sm:px-8 pb-10">
        <div className="max-w-[800px] mx-auto space-y-4">
          {estado.tipo === "carregando" && !par && (
            <p className="py-16 text-center text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "14.9px" }}>
              Carregando...
            </p>
          )}

          {estado.tipo === "restrito" && (
            <Aviso titulo={estado.mensagem} />
          )}

          {estado.tipo === "erro" && (
            <Aviso titulo={estado.mensagem}>
              <button
                onClick={() => void carregar()}
                className="mt-4 rounded-lg px-4 py-2 bg-[#1A3A5C] text-white hover:bg-[#1E4570] transition-colors"
                style={{ fontSize: "14.4px", fontWeight: 500 }}
              >
                Tentar de novo
              </button>
            </Aviso>
          )}

          {estado.tipo === "ok" && !estado.fila.par && <Aviso titulo="Tudo rotulado. Obrigado!" />}

          {par && (
            <>
              <Cartao titulo="Tese">
                <Campo rotulo="Pedido principal" valor={par.tese.pedido_principal} />
                <Campo rotulo="Tese central" valor={par.tese.tese_central} />
                {par.tese.normas.length > 0 && (
                  <div>
                    <Rotulo>Normas</Rotulo>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {par.tese.normas.map((n) => (
                        <span
                          key={n}
                          className="px-2.5 py-1 rounded-full bg-[#EFF4FA] dark:bg-[#1A2A3C] text-[#1A3A5C] dark:text-[#8AB0DC]"
                          style={{ fontSize: "12.6px" }}
                        >
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </Cartao>

              <Cartao titulo="Acórdão">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
                  <span className="font-mono">{par.documento.numero_processo ?? "Processo não encontrado"}</span>
                  {par.documento.tribunal && <span>{par.documento.tribunal}</span>}
                  {par.documento.link_original && (
                    <a
                      href={par.documento.link_original}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline"
                    >
                      Ver inteiro teor
                      <ExternalLink className="w-3 h-3" strokeWidth={2} />
                    </a>
                  )}
                </div>
                <Campo rotulo="Ementa" valor={par.documento.ementa} />
                <Campo rotulo="Fundamentação (trecho)" valor={par.documento.fundamentacao_inicio} />
              </Cartao>

              <Cartao titulo="Quão relevante é este acórdão para a tese?">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {RELEVANCIAS.map((r) => (
                    <Opcao
                      key={r.valor}
                      ativo={relevancia === r.valor}
                      desabilitado={enviando}
                      onClick={() => escolherRelevancia(r.valor)}
                      rotulo={r.rotulo}
                      dica={r.tecla}
                    />
                  ))}
                </div>
                <div>
                  <Rotulo>O acórdão sustenta a tese?</Rotulo>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {STANCES.map((s) => (
                      <Opcao
                        key={s.valor}
                        ativo={stance === s.valor}
                        desabilitado={enviando}
                        onClick={() => escolherStance(s.valor)}
                        rotulo={s.rotulo}
                        dica={s.tecla.toUpperCase()}
                      />
                    ))}
                  </div>
                </div>
                <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12.6px" }}>
                  Atalhos: 1-4 para a relevância, F / E / N para a stance. O rótulo é enviado quando os dois estão escolhidos.
                </p>
                {enviando && (
                  <p className="text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "13.2px" }}>
                    Enviando...
                  </p>
                )}
                {erroEnvio && (
                  <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-[#E8C4C4] dark:border-[#4A2A2C] bg-[#FBF0F0] dark:bg-[#2A1517] px-3 py-2">
                    <span className="text-[#C44040] dark:text-[#D96B6B]" style={{ fontSize: "13.8px" }}>
                      {erroEnvio}
                    </span>
                    <button
                      onClick={() => void enviar()}
                      className="text-[#C44040] dark:text-[#D96B6B] underline flex-shrink-0"
                      style={{ fontSize: "13.8px" }}
                    >
                      Tentar de novo
                    </button>
                  </div>
                )}
              </Cartao>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Aviso({ titulo, children }: { titulo: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-8 py-20 text-center">
      <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "17.2px", fontWeight: 600 }}>
        {titulo}
      </h2>
      {children}
    </div>
  );
}

function Cartao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="bg-white dark:bg-[#17171B] rounded-xl border border-[#E4E4EC] dark:border-[#26262C] shadow-[0_1px_6px_rgba(0,0,0,0.04)] dark:shadow-none px-5 py-4 space-y-3">
      <h2 className="text-[#0F1117] dark:text-[#ECECEF]" style={{ fontSize: "16.1px", fontWeight: 600 }}>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[#AEAEBF] dark:text-[#6E6E7C] uppercase tracking-[0.06em]" style={{ fontSize: "12.1px", fontWeight: 600 }}>
      {children}
    </p>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string | null }) {
  return (
    <div>
      <Rotulo>{rotulo}</Rotulo>
      <p className="mt-1 whitespace-pre-line text-[#4A4A5A] dark:text-[#C4C4CE]" style={{ fontSize: "14.9px", lineHeight: 1.6 }}>
        {valor || "—"}
      </p>
    </div>
  );
}

function Opcao(props: { ativo: boolean; desabilitado: boolean; onClick: () => void; rotulo: string; dica: string }) {
  return (
    <button
      onClick={props.onClick}
      disabled={props.desabilitado}
      aria-pressed={props.ativo}
      aria-keyshortcuts={props.dica}
      className={`rounded-lg border px-3 py-2.5 text-left transition-colors disabled:opacity-60 ${
        props.ativo
          ? "bg-[#1A3A5C] border-[#1A3A5C] text-white"
          : "bg-white dark:bg-[#17171B] border-[#E0E0EA] dark:border-[#2A2A32] text-[#4A4A5A] dark:text-[#C4C4CE] hover:border-[#1A3A5C] dark:hover:border-[#8AB0DC]"
      }`}
      style={{ fontSize: "14.4px", fontWeight: 500 }}
    >
      {props.rotulo}
    </button>
  );
}
