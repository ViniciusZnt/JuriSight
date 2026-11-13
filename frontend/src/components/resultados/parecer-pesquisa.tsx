"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, CheckCircle2, ClipboardCheck, Copy, Info, MessageSquareText, Scale, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { ActionButton } from "@/components/ui/action-button";
import { explicarBusca, type EstruturaArgumentativa, type ExplicacaoBusca, type FraseResposta, type ResultCard } from "@/lib/api";
import { dispositivoETexto, itensDaFrase, orgaosCitados, respostaParaCopiar, vereditoDe } from "@/lib/decision-view";
import { useCopiar } from "@/lib/use-copiar";
import { FEEDBACK_KEY, lerVotos, type useRespostaGerada } from "@/components/resultados/resposta-gerada";
import { BUSCA, TOTAL_ACERVO } from "@/lib/cores-busca";

const LIMITE_TERMOS = 4;
const LIMITE_FUNDAMENTOS = 3; // o modelo às vezes escreve um por turma; o resto fica atrás de "Mais N"

const maiuscula = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

/** "#2 · #9": números pequenos que levam ao card. */
function Numeros({ citacoes, porNumero, onIr }: { citacoes: number[]; porNumero: Map<number, ResultCard>; onIr: (id: string) => void }) {
  const validas = citacoes.filter((n) => porNumero.has(n));
  if (!validas.length) return null;
  return (
    <span className="ml-1.5 whitespace-nowrap text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "11.4px", fontWeight: 600 }}>
      {validas.map((n, i) => {
        const d = porNumero.get(n)!;
        return (
          <span key={n}>
            {i > 0 && " · "}
            <a
              href={`#decisao-${d.id}`}
              onClick={() => onIr(d.id)}
              title={`${d.tribunal} · ${d.turma} · ${d.numero_processo}`}
              className="hover:text-[#1A3A5C] dark:hover:text-[#8AB0DC] no-underline"
            >
              #{n}
            </a>
          </span>
        );
      })}
    </span>
  );
}

function Linha({ icone: Icone, rotulo, tom = "neutro", children }: {
  icone: typeof Scale;
  rotulo: string;
  tom?: "neutro" | "resposta" | "atencao";
  children: React.ReactNode;
}) {
  const fundo = tom === "resposta" ? "bg-[#F1F8F4] dark:bg-[#12211A]" : tom === "atencao" ? "bg-[#FCF7EF] dark:bg-[#231B10]" : "";
  const corRotulo =
    tom === "resposta" ? "text-[#2D8A5F] dark:text-[#3DA372]" : tom === "atencao" ? "text-[#A8661F] dark:text-[#E0AC6C]" : "text-[#1A3A5C] dark:text-[#8AB0DC]";
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-[140px_minmax(0,1fr)] border-t first:border-t-0 border-[#EEF0F5] dark:border-[#26262C] ${fundo}`}>
      <p className={`flex items-start gap-2 px-6 sm:pr-0 pt-4 sm:pb-4 uppercase tracking-[0.06em] ${corRotulo}`} style={{ fontSize: "11.5px", fontWeight: 700 }}>
        <Icone className="w-3.5 h-3.5 mt-px flex-shrink-0" strokeWidth={1.8} />
        {rotulo}
      </p>
      <div className="min-w-0 px-6 sm:pl-1 sm:pr-7 pt-1.5 sm:pt-[15px] pb-4 text-[#33333F] dark:text-[#D4D4DC] leading-[1.68]" style={{ fontSize: "14.8px" }}>
        {children}
      </div>
    </div>
  );
}

function Lista({ children }: { children: React.ReactNode }) {
  return <ul className="space-y-2 list-none [&>li]:relative [&>li]:pl-4 [&>li]:before:absolute [&>li]:before:left-0.5 [&>li]:before:top-[0.72em] [&>li]:before:w-[5px] [&>li]:before:h-[5px] [&>li]:before:rounded-full [&>li]:before:bg-[#C8D9EF] dark:[&>li]:before:bg-[#2A3A4C]">{children}</ul>;
}

interface Props {
  estrutura: EstruturaArgumentativa;
  /** null = busca sem filtro restrito; total null = contagem do acervo indisponível. */
  filtro: { itens: string[]; total: number | null } | null;
  resposta: ReturnType<typeof useRespostaGerada>;
  /** Resultados na ordem da numeração dos cards (#1 = ordem[0]). */
  ordem: ResultCard[];
  onIr: (id: string) => void;
  /** Quando não há decisões para responder, o porquê (no lugar da resposta). */
  semResposta?: string;
}

/** O parecer da pesquisa num card só: a faixa azul diz como a busca foi feita (filtro restrito
 *  com o total do acervo, busca semântica e termos do BM25) e, abaixo, a resposta gerada pela IA
 *  em linhas — resposta, por quê, o que provar, base legal e atenção —, com o órgão de quem
 *  decidiu e os números #N que levam aos cards. */
export function ParecerPesquisa({ estrutura, filtro, resposta: { chave, vazia, estado }, ordem, onIr, semResposta }: Props) {
  const [explicacao, setExplicacao] = useState<ExplicacaoBusca | null>(null);
  const [erroExplicacao, setErroExplicacao] = useState(false);
  const [todosTermos, setTodosTermos] = useState(false);
  const [todosFundamentos, setTodosFundamentos] = useState(false);
  const [copiada, copiar] = useCopiar();
  const [votos, setVotos] = useState(lerVotos);
  const voto = votos[chave];

  // a página remonta o card (key) quando a estrutura muda, então basta pedir uma vez
  useEffect(() => {
    let vivo = true;
    explicarBusca(estrutura)
      .then((e) => vivo && setExplicacao(e))
      .catch(() => vivo && setErroExplicacao(true));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const porNumero = new Map(ordem.map((d, i) => [i + 1, d]));
  const frases = estado.status === "ok" ? estado.resposta.frases : [];
  const de = (tipo: FraseResposta["tipo"]) => frases.filter((f) => f.tipo === tipo);
  const [respostas, fundamentos, baseLegal, prova, divergencia] = [de("resposta"), de("fundamento"), de("base_legal"), de("prova"), de("divergencia")];
  const nums = (f: FraseResposta) => <Numeros citacoes={f.citacoes} porNumero={porNumero} onIr={onIr} />;
  const termos = explicacao?.termos ?? [];
  const termosVisiveis = todosTermos ? termos : termos.slice(0, LIMITE_TERMOS);

  const votar = (v: "util" | "nao_util") => {
    const novos = { ...lerVotos() };
    if (voto === v) delete novos[chave];
    else novos[chave] = v;
    setVotos(novos);
    try {
      localStorage.setItem(FEEDBACK_KEY, JSON.stringify(novos));
    } catch {
      /* localStorage indisponível: o voto vale só nesta tela */
    }
  };

  const colunas = filtro ? "md:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)_minmax(0,1.15fr)]" : "md:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]";
  const coluna = "min-w-0 py-2.5 md:py-0 md:px-4 first:md:pl-0 last:md:pr-0 border-t md:border-t-0 md:border-l first:border-t-0 first:md:border-l-0 border-white/15";
  const tituloColuna = "flex items-center gap-2 mb-2 text-[#AFC6E3]";
  const temResposta = estado.status === "ok" && frases.length > 0;

  return (
    <section
      aria-label="Resposta da pesquisa"
      aria-busy={estado.status === "carregando" && !vazia}
      className="w-full max-w-[800px] mb-6 bg-white dark:bg-[#17171B] rounded-[14px] border border-[#DDE3EC] dark:border-[#26262C] shadow-[0_4px_18px_rgba(15,17,23,0.07)] dark:shadow-none overflow-hidden"
    >
      {/* Faixa azul: como esta busca foi feita */}
      <div role="region" aria-label="Como esta busca foi feita" className="relative px-6 pt-4 pb-[18px] bg-gradient-to-b from-[#1A3A5C] to-[#1D4166] dark:from-[#132A44] dark:to-[#15304D] text-[#EEF3FA]">
        <p className="flex items-center gap-2 mb-3 text-[#AFC6E3] uppercase tracking-[0.07em]" style={{ fontSize: "11.5px", fontWeight: 700 }}>
          <span className="grid place-items-center w-[22px] h-[22px] rounded-md bg-white/10 text-white">
            <Search className="w-[13px] h-[13px]" strokeWidth={1.9} />
          </span>
          Como esta busca foi feita
        </p>
        <div className={`grid grid-cols-1 ${colunas}`}>
          {filtro && (
            <div className={coluna}>
              <p className={tituloColuna} style={{ fontSize: "12px", fontWeight: 600 }}>
                <span className="w-2 h-2 rounded-sm bg-white" />Filtro restrito
              </p>
              <div>
                {filtro.itens.map((t) => (
                  <span key={t} className="inline-block bg-white text-[#1A3A5C] rounded-[7px] px-[9px] mr-[5px] mb-1.5 leading-6 shadow-[0_1px_3px_rgba(0,0,0,0.2)]" style={{ fontSize: "13.6px", fontWeight: 700 }}>
                    {t}
                  </span>
                ))}
              </div>
              {filtro.total !== null && (
                <div className="mt-1">
                  <span className="text-white tabular-nums" style={{ fontSize: "18px", fontWeight: 700 }}>{filtro.total.toLocaleString("pt-BR")}</span>{" "}
                  <span className="text-[#AFC6E3]" style={{ fontSize: "12.4px" }}>de {TOTAL_ACERVO.toLocaleString("pt-BR")} decisões</span>
                  <div className="h-1 rounded-full bg-white/15 mt-1.5 overflow-hidden" aria-hidden>
                    <div className="h-full rounded-full bg-white min-w-[3px]" style={{ width: `${(100 * filtro.total) / TOTAL_ACERVO}%` }} />
                  </div>
                  <p className="mt-1 text-[#AFC6E3]" style={{ fontSize: "11.6px" }}>só elas foram ordenadas</p>
                </div>
              )}
            </div>
          )}
          <div className={coluna}>
            <p className={tituloColuna} style={{ fontSize: "12px", fontWeight: 600 }}>
              <span className={`w-2 h-2 rounded-sm ${BUSCA.semantica.pontoSobreMarinho}`} />{BUSCA.semantica.nome}
            </p>
            <p className="pl-2.5 border-l-2 leading-relaxed" style={{ fontSize: "13.6px", borderColor: BUSCA.semantica.corSobreMarinho }}>
              {explicacao ? explicacao.semantica : erroExplicacao ? "Não foi possível carregar." : "Carregando…"}
            </p>
          </div>
          <div className={coluna}>
            <p className={tituloColuna} style={{ fontSize: "12px", fontWeight: 600 }}>
              <span className={`w-2 h-2 rounded-sm ${BUSCA.termos.pontoSobreMarinho}`} />{BUSCA.termos.nome}
            </p>
            {explicacao && termos.length === 0 && (
              <p className="text-[#AFC6E3]" style={{ fontSize: "13px" }}>Nenhum termo exato: só a busca semântica contou.</p>
            )}
            <div>
              {termosVisiveis.map((t) => (
                <span key={t} className="inline-block rounded-md border border-[#5FCFC4]/45 bg-[#0E8A80]/25 text-[#D4F3EF] px-[7px] mr-1 mb-[5px] leading-[21px]" style={{ fontSize: "12.8px" }}>
                  {t}
                </span>
              ))}
              {termos.length > LIMITE_TERMOS && !todosTermos && (
                <button
                  onClick={() => setTodosTermos(true)}
                  title="Mostrar todos os termos"
                  className="inline-block rounded-md border border-dashed border-white/35 text-[#AFC6E3] hover:text-white px-[7px] mb-[5px] leading-[21px]"
                  style={{ fontSize: "12.8px" }}
                >
                  +{termos.length - LIMITE_TERMOS}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* A resposta da IA, em linhas */}
      {vazia ? (
        semResposta && (
          <Linha icone={MessageSquareText} rotulo="Resposta">
            <span className="text-[#8A8A9A] dark:text-[#9494A2]">{semResposta}</span>
          </Linha>
        )
      ) : estado.status === "carregando" ? (
        <Linha icone={MessageSquareText} rotulo="Resposta" tom="resposta">
          <div className="space-y-2.5 animate-pulse pt-1" aria-label="Gerando a resposta a partir das decisões…">
            {["w-full", "w-11/12", "w-3/4"].map((w, i) => (
              <div key={i} className={`h-3.5 rounded bg-[#DCEBE2] dark:bg-[#1E3A2C] ${w}`} />
            ))}
          </div>
        </Linha>
      ) : estado.status === "erro" ? (
        <Linha icone={MessageSquareText} rotulo="Resposta">
          <span className="text-[#8A8A9A] dark:text-[#9494A2]">Resposta gerada indisponível: {estado.mensagem}</span>
        </Linha>
      ) : temResposta ? (
        <>
          {respostas.map((f, i) => {
            const { veredito, resto } = vereditoDe(f.texto);
            const cor = veredito === "Não" ? "text-[#C44040] dark:text-[#D96B6B]" : veredito === "Depende" ? "text-[#A8661F] dark:text-[#E0AC6C]" : "text-[#2D8A5F] dark:text-[#3DA372]";
            return (
              <Linha key={i} icone={MessageSquareText} rotulo="Resposta" tom="resposta">
                <p className="text-[#0F1117] dark:text-[#ECECEF] leading-normal" style={{ fontSize: "17.5px", fontWeight: 600 }}>
                  {veredito && <span className={cor}>{veredito}{/^\p{Ll}/u.test(resto) ? " " : ". "}</span>}
                  {resto}
                  {nums(f)}
                </p>
              </Linha>
            );
          })}
          {fundamentos.length > 0 && (
            <Linha icone={Scale} rotulo="Por quê">
              <Lista>
                {(todosFundamentos ? fundamentos : fundamentos.slice(0, LIMITE_FUNDAMENTOS)).map((f, i) => {
                  const citadas = f.citacoes.map((n) => porNumero.get(n)).filter((d): d is ResultCard => !!d);
                  return (
                    <li key={i}>
                      {maiuscula(f.texto).replace(/\.$/, "")}
                      {citadas.length > 0 && (
                        <>
                          {" — "}
                          <a
                            href={`#decisao-${citadas[0].id}`}
                            onClick={() => onIr(citadas[0].id)}
                            className="text-[#1A3A5C] dark:text-[#8AB0DC] border-b border-[#C8D9EF] dark:border-[#2A3A4C] hover:border-[#1A3A5C] no-underline"
                            style={{ fontWeight: 600 }}
                          >
                            {orgaosCitados(citadas)}
                          </a>
                        </>
                      )}
                      {nums(f)}
                    </li>
                  );
                })}
              </Lista>
              {!todosFundamentos && fundamentos.length > LIMITE_FUNDAMENTOS && (
                <button
                  type="button"
                  onClick={() => setTodosFundamentos(true)}
                  className="mt-1.5 ml-4 text-[#1A3A5C] dark:text-[#8AB0DC] hover:underline underline-offset-2"
                  style={{ fontSize: "13px", fontWeight: 600 }}
                >
                  Mais {fundamentos.length - LIMITE_FUNDAMENTOS} fundamentos
                </button>
              )}
            </Linha>
          )}
          {prova.map((f, i) => {
            const itens = itensDaFrase(f.texto, true);
            return (
              <Linha key={`p${i}`} icone={ClipboardCheck} rotulo="O que provar">
                <Lista>
                  {itens.map((item, k) => (
                    <li key={k}>
                      {item}
                      {k === itens.length - 1 && nums(f)}
                    </li>
                  ))}
                </Lista>
              </Linha>
            );
          })}
          {baseLegal.map((f, i) => {
            const itens = itensDaFrase(f.texto);
            return (
              <Linha key={`b${i}`} icone={BookOpen} rotulo="Base legal">
                <Lista>
                  {itens.map((item, k) => {
                    const [dispositivo, texto] = dispositivoETexto(item);
                    return (
                      <li key={k}>
                        {dispositivo && (
                          <>
                            <span className="text-[#1A3A5C] dark:text-[#8AB0DC]" style={{ fontWeight: 600 }}>{dispositivo}</span>
                            {": "}
                          </>
                        )}
                        {texto}
                        {k === itens.length - 1 && nums(f)}
                      </li>
                    );
                  })}
                </Lista>
              </Linha>
            );
          })}
          {divergencia.length > 0 && (
            <Linha icone={AlertTriangle} rotulo="Atenção" tom="atencao">
              <div className="space-y-1.5">
                {divergencia.map((f, i) => (
                  <p key={i}>
                    {f.texto}
                    {nums(f)}
                  </p>
                ))}
              </div>
            </Linha>
          )}
        </>
      ) : null}

      {temResposta && (
        <div className="flex flex-wrap items-center gap-2 px-6 py-2.5 border-t border-[#EEF0F5] dark:border-[#26262C] bg-[#FCFCFD] dark:bg-[#1A1A1F]">
          <ActionButton
            icon={copiada ? CheckCircle2 : Copy}
            label={copiada ? "Copiada!" : "Copiar resposta"}
            tone={copiada ? "success" : "neutral"}
            size="sm"
            title="Copiar a resposta com as citações (tribunal, turma, processo, data)"
            onClick={() => copiar(respostaParaCopiar(frases, porNumero))}
          />
          {(
            [
              ["util", ThumbsUp, "Resposta útil"],
              ["nao_util", ThumbsDown, "Resposta não útil"],
            ] as const
          ).map(([v, Icone, rotulo]) => (
            <button
              key={v}
              onClick={() => votar(v)}
              aria-pressed={voto === v}
              aria-label={rotulo}
              title={rotulo}
              className={`flex items-center justify-center w-[30px] h-[30px] rounded-lg border transition-all ${
                voto === v
                  ? "bg-[#EFF4FA] dark:bg-[#1A2A3C] border-[#C8D9EF] dark:border-[#2A3A4C] text-[#1A3A5C] dark:text-[#8AB0DC]"
                  : "bg-white dark:bg-[#1C1C21] border-[#E0E0EA] dark:border-[#26262C] text-[#6B6B80] dark:text-[#A6A6B4] hover:border-[#1A3A5C]/30"
              }`}
            >
              <Icone className="w-3.5 h-3.5" strokeWidth={1.8} fill={voto === v ? "currentColor" : "none"} />
            </button>
          ))}
          <span className="sm:ml-auto flex items-center gap-1.5 text-[#8A8A9A] dark:text-[#9494A2]" style={{ fontSize: "12px" }}>
            <Info className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={1.8} />
            Gerada por IA a partir das decisões listadas. Confira as citações.
          </span>
        </div>
      )}
    </section>
  );
}
