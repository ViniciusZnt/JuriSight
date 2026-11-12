"use client";

import { useEffect, useRef, useState } from "react";
import { Pencil, X } from "lucide-react";
import { contarFiltros, listarTribunais, rotuloTribunal, sugerirDispositivos, ROTULO_FASE, type ContagemFiltros, type Fase, type ExpressaoSugerida, type SugestaoDispositivo } from "@/lib/api";

const DEBOUNCE_MS = 250;

const chipCls =
  "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 bg-[#EEF3FB] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]";
const inputCls =
  "w-full rounded-lg border border-[#E4E4EC] dark:border-[#26262C] bg-[#FAFAFA] dark:bg-[#1C1C21] px-3 py-2 outline-none text-[#1A1A2A] dark:text-[#ECECEF] placeholder:text-[#C0C0CE] dark:placeholder:text-[#4A4A54] focus:border-[#1A3A5C] dark:focus:border-[#8AB0DC]";
const mutedCls = "text-[#AEAEBF] dark:text-[#6E6E7C]";

function Chip({ children, onRemove, onEdit, label }: { children: React.ReactNode; onRemove: () => void; onEdit: () => void; label: string }) {
  return (
    <div className={chipCls} style={{ fontSize: "13.8px", fontWeight: 500 }}>
      {children}
      <button onClick={onEdit} aria-label={`Editar ${label}`} className="opacity-50 hover:opacity-100">
        <Pencil style={{ width: "10px", height: "10px" }} strokeWidth={2} />
      </button>
      <button onClick={onRemove} aria-label={`Remover ${label}`} className="opacity-50 hover:opacity-100">
        <X style={{ width: "10px", height: "10px" }} strokeWidth={2.5} />
      </button>
    </div>
  );
}

/** Filtro restrito da Revisão: dispositivos legais (autocompletar no acervo) e expressões
 *  obrigatórias, com a contagem de decisões que cumprem cada um e todos juntos. */
/** Sugestões da IA (já conferidas no acervo): botões "+ … · N decisões"; viram filtro só no clique. */
function SugestoesDaIa({ itens, onEscolher }: { itens: { rotulo: string; total: number }[]; onEscolher: (i: number) => void }) {
  if (!itens.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2">
      <span className={mutedCls} style={{ fontSize: "12.6px" }}>Sugestões da IA:</span>
      {itens.map((s, i) => (
        <button
          key={s.rotulo}
          onClick={() => onEscolher(i)}
          className="px-2.5 py-1 rounded-lg border border-dashed border-[#BDE0CF] dark:border-[#1E4A34] text-[#1A5C3A] dark:text-[#6FCB9A] hover:bg-[#EDF7F2] dark:hover:bg-[#122A1E] transition-colors"
          style={{ fontSize: "13px" }}
        >
          {`+ ${s.rotulo} · ${s.total} decisões`}
        </button>
      ))}
    </div>
  );
}

export function FiltroRestrito({
  dispositivos,
  expressoes,
  tribunais,
  fase,
  dispositivosIa,
  expressoesSugeridas = [],
  dispositivosSugeridos = [],
  onChange,
}: {
  dispositivos: string[];
  expressoes: string[];
  tribunais: string[];
  fase: Fase | null;
  dispositivosIa: string[];
  /** Sugeridas pela IA (e já conferidas no acervo): só viram filtro com o clique do advogado. */
  expressoesSugeridas?: ExpressaoSugerida[];
  /** Dispositivos que a IA relaciona ao tema, também só sob clique. */
  dispositivosSugeridos?: SugestaoDispositivo[];
  onChange: (patch: { dispositivos?: string[]; expressoes?: string[]; tribunais?: string[]; fase?: Fase | null }) => void;
}) {
  const [busca, setBusca] = useState("");
  // última resposta das sugestões e de qual busca ela é (null em `opcoes` = falhou)
  const [sugestoes, setSugestoes] = useState<{ q: string; opcoes: SugestaoDispositivo[] | null } | null>(null);
  const [expr, setExpr] = useState("");
  // última contagem recebida e de qual filtro ela é (null em `dados` = falhou)
  const [recebida, setRecebida] = useState<{ chave: string; dados: ContagemFiltros | null } | null>(null);
  const [rotulos, setRotulos] = useState<Record<string, string>>({});
  // lista dos tribunais do acervo: carregada na primeira vez que o menu abre (null = ainda não / falhou)
  const [menuTribunais, setMenuTribunais] = useState(false);
  const [listaTribunais, setListaTribunais] = useState<{ tribunal: string; rotulo: string; total: number }[] | null>(null);
  const buscaRef = useRef<HTMLInputElement>(null);
  const exprRef = useRef<HTMLInputElement>(null);

  const q = busca.trim();
  useEffect(() => {
    if (!q) return;
    let ativo = true;
    const t = setTimeout(() => {
      sugerirDispositivos(q)
        .then((r) => ativo && setSugestoes({ q, opcoes: r }))
        .catch(() => ativo && setSugestoes({ q, opcoes: null }));
    }, DEBOUNCE_MS);
    return () => {
      ativo = false;
      clearTimeout(t);
    };
  }, [q]);

  // Só vale a resposta da busca que está no campo: a de uma busca anterior não aparece.
  const daBusca = q && sugestoes?.q === q ? sugestoes : null;
  const opcoes = daBusca?.opcoes ?? [];
  const semOpcoes = !daBusca ? null : daBusca.opcoes === null ? "erro" : daBusca.opcoes.length ? null : "vazio";

  const chave = JSON.stringify([dispositivos, expressoes, tribunais, fase]);
  useEffect(() => {
    if (!dispositivos.length && !expressoes.length && !tribunais.length && !fase) return;
    let ativo = true;
    const t = setTimeout(() => {
      contarFiltros({ dispositivos, expressoes, tribunais, fase })
        .then((r) => ativo && setRecebida({ chave, dados: r }))
        .catch(() => ativo && setRecebida({ chave, dados: null }));
    }, DEBOUNCE_MS);
    return () => {
      ativo = false;
      clearTimeout(t);
    };
    // `chave` resume dispositivos, expressões, tribunais e fase
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  // O total combinado só vale para o filtro atual: enquanto a contagem nova não chega, "contando…".
  // O total de cada chip não depende dos outros filtros, então o da última contagem continua certo.
  const temFiltro = dispositivos.length > 0 || expressoes.length > 0 || tribunais.length > 0 || fase !== null;
  const atual = temFiltro && recebida?.chave === chave ? recebida : null;
  const contagem = atual?.dados ?? null;
  const indisponivel = atual !== null && atual.dados === null;
  const contando = temFiltro && atual === null;
  const ultima = recebida?.dados;
  const rotulo = (codigo: string) => rotulos[codigo] ?? ultima?.dispositivos.find((d) => d.codigo === codigo)?.rotulo ?? codigo;
  const totalExpr = (texto: string) => ultima?.expressoes.find((e) => e.texto === texto)?.total;

  const escolher = (o: SugestaoDispositivo) => {
    const codigo = o.codigo;
    setRotulos((r) => ({ ...r, [codigo]: o.rotulo }));
    if (!dispositivos.includes(codigo)) onChange({ dispositivos: [...dispositivos, codigo] });
    setBusca("");
  };

  const sugeridasRestantes = expressoesSugeridas.filter((s) => !expressoes.includes(s.texto));
  const dispositivosRestantes = dispositivosSugeridos.filter((d) => !dispositivos.includes(d.codigo));

  const abrirTribunais = () => {
    setMenuTribunais((a) => !a);
    if (!listaTribunais) listarTribunais().then(setListaTribunais).catch(() => setListaTribunais(null));
  };
  const alternarTribunal = (t: string) => onChange({ tribunais: tribunais.includes(t) ? tribunais.filter((x) => x !== t) : [...tribunais, t] });

  const addExpr = () => {
    const t = expr.trim();
    if (t && !expressoes.includes(t)) onChange({ expressoes: [...expressoes, t] });
    setExpr("");
  };

  return (
    <div className="p-4 rounded-xl border border-[#C8D9EF] dark:border-[#2A3A4C] bg-[#F5F8FD] dark:bg-[#131C28]">
      <h3 className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "14.9px", fontWeight: 700 }}>
        Filtro restrito
      </h3>
      <p className="text-[#7A7A8E] dark:text-[#9E9EAC] mb-4" style={{ fontSize: "13.2px" }}>
        Só entram decisões que citam todos os dispositivos, contêm todas as expressões e são do tribunal e da fase escolhidos. Os outros campos orientam a busca livre.
      </p>

      <div className="mb-4">
        <div className="mb-2 text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
          Dispositivos legais
        </div>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {dispositivos.map((c) => (
            <Chip
              key={c}
              label={rotulo(c)}
              onRemove={() => onChange({ dispositivos: dispositivos.filter((x) => x !== c) })}
              onEdit={() => {
                onChange({ dispositivos: dispositivos.filter((x) => x !== c) });
                setBusca(rotulo(c));
                buscaRef.current?.focus();
              }}
            >
              <span>{rotulo(c)}</span>
              {dispositivosIa.includes(c) && (
                <span className="rounded px-1.5 bg-[#EDF7F2] dark:bg-[#122A1E] text-[#1A5C3A] dark:text-[#6FCB9A]" style={{ fontSize: "11px" }}>
                  sugestão da IA
                </span>
              )}
            </Chip>
          ))}
        </div>
        <div className="relative">
          <input
            ref={buscaRef}
            aria-label="Buscar dispositivo legal"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar dispositivo (ex: CLT 59, Súmula 85)…"
            className={inputCls}
            style={{ fontSize: "14px" }}
          />
          {opcoes.length > 0 && (
            <ul className="absolute z-10 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-lg border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] shadow-lg">
              {opcoes.map((o) => (
                <li key={o.codigo}>
                  <button
                    onClick={() => escolher(o)}
                    className="w-full text-left px-3 py-2 text-[#1A1A2A] dark:text-[#ECECEF] hover:bg-[#EEF3FB] dark:hover:bg-[#1A2A3C]"
                    style={{ fontSize: "13.8px" }}
                  >
                    {`${o.rotulo} · ${o.total} decisões`}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {semOpcoes === "erro" && (
          <p className="mt-1 text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>
            Filtro restrito indisponível no momento
          </p>
        )}
        {semOpcoes === "vazio" && (
          <p className={`mt-1 ${mutedCls}`} style={{ fontSize: "13.2px" }}>
            {`Nenhum dispositivo do acervo para “${q}”. Normas fora da lista (ex.: NRs) vão em Outras normas ou em Expressões obrigatórias.`}
          </p>
        )}
        <SugestoesDaIa itens={dispositivosRestantes} onEscolher={(i) => escolher(dispositivosRestantes[i])} />
      </div>

      <div className="mb-3">
        <div className="mb-2 text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
          Expressões obrigatórias
        </div>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {expressoes.map((t) => (
            <Chip
              key={t}
              label={t}
              onRemove={() => onChange({ expressoes: expressoes.filter((x) => x !== t) })}
              onEdit={() => {
                onChange({ expressoes: expressoes.filter((x) => x !== t) });
                setExpr(t);
                exprRef.current?.focus();
              }}
            >
              <span>{t}</span>
              {totalExpr(t) !== undefined && <span className={mutedCls}>{`· ${totalExpr(t)} decisões`}</span>}
            </Chip>
          ))}
        </div>
        <input
          ref={exprRef}
          aria-label="Nova expressão obrigatória"
          value={expr}
          onChange={(e) => setExpr(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addExpr()}
          onBlur={addExpr} // como nos outros campos: texto digitado não se perde ao clicar em Buscar
          maxLength={200}
          placeholder="Expressão que a decisão deve conter (Enter para adicionar)"
          className={inputCls}
          style={{ fontSize: "14px" }}
        />
        <SugestoesDaIa
          itens={sugeridasRestantes.map((s) => ({ rotulo: s.texto, total: s.total }))}
          onEscolher={(i) => onChange({ expressoes: [...expressoes, sugeridasRestantes[i].texto] })}
        />
      </div>

      <div className="mb-3">
        <div className="mb-2 text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
          Tribunal
        </div>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {tribunais.map((t) => (
            <div key={t} className={chipCls} style={{ fontSize: "13.8px", fontWeight: 500 }}>
              <span>{rotuloTribunal(t)}</span>
              <button onClick={() => alternarTribunal(t)} aria-label={`Remover ${rotuloTribunal(t)}`} className="opacity-50 hover:opacity-100">
                <X style={{ width: "10px", height: "10px" }} strokeWidth={2.5} />
              </button>
            </div>
          ))}
        </div>
        <div className="relative max-w-full">
          <button
            onClick={abrirTribunais}
            aria-expanded={menuTribunais}
            className={`${inputCls} text-left`}
            style={{ fontSize: "14px" }}
          >
            Todos os tribunais
          </button>
          {menuTribunais && (
            <ul className="absolute z-10 left-0 right-0 max-w-full mt-1 max-h-56 overflow-y-auto rounded-lg border border-[#E4E4EC] dark:border-[#26262C] bg-white dark:bg-[#17171B] shadow-lg">
              {listaTribunais === null && (
                <li className={`px-3 py-2 ${mutedCls}`} style={{ fontSize: "13.2px" }}>Carregando tribunais…</li>
              )}
              {listaTribunais?.map((o) => (
                <li key={o.tribunal}>
                  <button
                    onClick={() => alternarTribunal(o.tribunal)}
                    aria-pressed={tribunais.includes(o.tribunal)}
                    className={`w-full text-left px-3 py-2 text-[#1A1A2A] dark:text-[#ECECEF] hover:bg-[#EEF3FB] dark:hover:bg-[#1A2A3C] ${tribunais.includes(o.tribunal) ? "bg-[#EEF3FB] dark:bg-[#1A2A3C] font-semibold" : ""}`}
                    style={{ fontSize: "13.8px" }}
                  >
                    {`${o.rotulo} · ${o.total} decisões`}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mb-3">
        <div className="mb-2 text-[#4A4A5A] dark:text-[#C4C4CE] tracking-[0.04em] uppercase" style={{ fontSize: "11.5px", fontWeight: 700 }}>
          Fase do processo
        </div>
        <div role="group" aria-label="Fase do processo" className="inline-flex flex-wrap p-[3px] gap-0.5 rounded-[10px] border border-[#E0E0EA] dark:border-[#2A2A32] bg-[#FAFAFC] dark:bg-[#1C1C21]">
          {([["Todas", null], ...(Object.keys(ROTULO_FASE) as Fase[]).map((f) => [ROTULO_FASE[f], f])] as [string, Fase | null][]).map(([rot, valor]) => {
            const ativo = fase === valor;
            return (
              <button
                key={rot}
                onClick={() => onChange({ fase: valor })}
                aria-pressed={ativo}
                className={`px-3 py-1.5 rounded-[7px] transition-all ${ativo ? "bg-[#1A3A5C] dark:bg-[#8AB0DC] text-white dark:text-[#0E0E11] shadow-[0_1px_6px_rgba(26,58,92,0.24)]" : "text-[#6B6B80] dark:text-[#A6A6B4] hover:bg-white dark:hover:bg-[#17171B]"}`}
                style={{ fontSize: "13.4px", fontWeight: ativo ? 600 : 400 }}
              >
                {rot}
              </button>
            );
          })}
        </div>
      </div>

      {indisponivel && (
        <p className="text-[#7A1A1A] dark:text-[#E08A93]" style={{ fontSize: "13.2px" }}>
          Filtro restrito indisponível no momento
        </p>
      )}
      {contando && (
        <p className={mutedCls} style={{ fontSize: "13.8px", fontWeight: 600 }}>
          Com todos os filtros: contando…
        </p>
      )}
      {contagem && (
        <>
          <p className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontSize: "13.8px", fontWeight: 600 }}>
            {`Com todos os filtros: ${contagem.total} decisões`}
          </p>
          {contagem.total === 0 && (
            <p className="text-[#6B3B0A] dark:text-[#E0AC6C]" style={{ fontSize: "13.2px" }}>
              Nenhuma decisão do acervo cumpre todos os filtros. A faixa restrita virá vazia.
            </p>
          )}
        </>
      )}
    </div>
  );
}
