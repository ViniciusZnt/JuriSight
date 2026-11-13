import Link from "next/link";
import type { ReactNode } from "react";
import {
  AlertTriangle, ArrowDown, ArrowDownWideNarrow, ArrowRight, Ban, BookOpen, Building2, Calendar, ChartNoAxesColumn,
  Check, Clock, Compass, Database, FileText, Filter, Hash, Info, Landmark, Layers, List, MessageSquare, PencilLine,
  Quote, Route, Scale, Search, ShieldCheck, Sparkles, Star, Target, Type, Upload, X, type LucideIcon,
} from "lucide-react";
import { BUSCA, TOTAL_ACERVO, type Busca } from "@/lib/cores-busca";

/** Guia de uso (/guia): sequência vertical que explica o caminho de uma busca, o que cada campo
 *  da Revisão de Contexto faz e os limites do MVP. Conteúdo estático; as cores das três buscas
 *  vêm de lib/cores-busca (as mesmas do painel dos resultados e da Revisão). */

const ACERVO = TOTAL_ACERVO.toLocaleString("pt-BR");
const ICONE_BUSCA: Record<Busca, LucideIcon> = { filtro: Filter, semantica: Compass, termos: Search };

// Tons de texto e superfícies do app (claro / escuro).
const NAVY_TXT = "text-[#1A3A5C] dark:text-[#8AB0DC]";
const TXT = "text-[#2B2D3A] dark:text-[#C4C4CE]";
const MUT = "text-[#5C5F70] dark:text-[#9E9EAC]";
const FORTE = "text-[#11131A] dark:text-[#ECECEF]";
const CARD = "bg-white dark:bg-[#17171B] border border-[#E4E4EC] dark:border-[#26262C] rounded-2xl shadow-[0_1px_2px_rgba(16,24,40,0.04),0_4px_12px_-8px_rgba(26,58,92,0.18)]";
const QUADRADO_NAVY = "bg-[#1A3A5C] text-white dark:bg-[#24476E]";

function Ic({ icon: Icon, className = "w-5 h-5" }: { icon: LucideIcon; className?: string }) {
  return <Icon aria-hidden="true" className={`${className} flex-none`} strokeWidth={2} />;
}

function Chave({ busca, sufixo }: { busca: Busca; sufixo?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 align-middle whitespace-nowrap ${BUSCA[busca].chip}`} style={{ fontSize: "12.5px", fontWeight: 700 }}>
      <Ic icon={ICONE_BUSCA[busca]} className="w-3.5 h-3.5" />
      {BUSCA[busca].nome}{sufixo}
    </span>
  );
}

function Mini({ icon, titulo, children }: { icon: LucideIcon; titulo: string; children: ReactNode }) {
  return (
    <div className={`${CARD} flex gap-3 items-start p-4 ${TXT}`} style={{ fontSize: "13.5px", lineHeight: 1.55 }}>
      <span className={`grid place-items-center w-10 h-10 rounded-[11px] flex-none ${QUADRADO_NAVY}`}><Ic icon={icon} /></span>
      <div className="min-w-0">
        <span className={`block mb-0.5 ${FORTE}`} style={{ fontSize: "14.5px", fontWeight: 700 }}>{titulo}</span>
        {children}
      </div>
    </div>
  );
}

function Nota({ icon, tom, children }: { icon: LucideIcon; tom: "navy" | "semantica" | "neutro"; children: ReactNode }) {
  const fundo = {
    navy: "bg-[#EEF3FA] dark:bg-[#15212F] text-[#1A3A5C] dark:text-[#AFC6E3]",
    semantica: "bg-[#F1EDFC] dark:bg-[#211A38] text-[#46308C] dark:text-[#C9BCF5]",
    neutro: `${CARD} ${TXT}`,
  }[tom];
  const icone = tom === "semantica" ? "bg-[#6D4FC2] text-white" : QUADRADO_NAVY;
  return (
    <div className={`flex gap-3 items-center rounded-xl px-3.5 py-3 mt-3 ${fundo}`} style={{ fontSize: "13.5px", lineHeight: 1.5, fontWeight: 500 }}>
      <span className={`grid place-items-center w-[30px] h-[30px] rounded-[9px] flex-none ${icone}`}><Ic icon={icon} className="w-4 h-4" /></span>
      <div>{children}</div>
    </div>
  );
}

function Chip({ busca, tracejado, children }: { busca?: Busca; tracejado?: boolean; children: ReactNode }) {
  const estilo = tracejado
    ? "bg-white dark:bg-transparent border-[1.5px] border-dashed border-[#8EA6C4] dark:border-[#4A5E78] text-[#34507A] dark:text-[#9DB6D6]"
    : `border ${BUSCA[busca ?? "filtro"].chip}`;
  return <span className={`inline-block rounded-lg px-2.5 py-1 ${estilo} ${busca === "semantica" ? "italic" : ""}`} style={{ fontSize: "13px", fontWeight: 500 }}>{children}</span>;
}

function FacaEvite({ faca, evite }: { faca: string; evite: string }) {
  const caixa = "flex gap-2 items-start rounded-[10px] px-2.5 py-2 bg-[#F4F5F8] dark:bg-[#1C1C21] border border-[#E8E9EF] dark:border-[#2A2A32]";
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3 ${TXT}`} style={{ fontSize: "13px", lineHeight: 1.45 }}>
      <div className={caixa}>
        <Ic icon={Check} className="w-4 h-4 mt-0.5 text-[#1F7A4D] dark:text-[#6FCB9A]" />
        <div><span className="block uppercase tracking-[0.06em] text-[#1F7A4D] dark:text-[#6FCB9A]" style={{ fontSize: "11px", fontWeight: 800 }}>Faça</span>{faca}</div>
      </div>
      <div className={caixa}>
        <Ic icon={X} className="w-4 h-4 mt-0.5 text-[#B23A3A] dark:text-[#E08A93]" />
        <div><span className="block uppercase tracking-[0.06em] text-[#B23A3A] dark:text-[#E08A93]" style={{ fontSize: "11px", fontWeight: 800 }}>Evite</span>{evite}</div>
      </div>
    </div>
  );
}

function Campo({ busca, icon, titulo, etiqueta, exemplos, faca, evite, children }: {
  busca: Busca; icon: LucideIcon; titulo: string; etiqueta?: string; exemplos: string[]; faca: string; evite: string; children?: ReactNode;
}) {
  return (
    <div className={`${CARD} grid grid-cols-[5px_1fr] overflow-hidden`}>
      <div className={BUSCA[busca].ponto} />
      <div className="px-4 py-3.5 min-w-0">
        <div className="flex flex-wrap justify-between items-center gap-2.5">
          <div className={`flex items-center gap-2.5 ${FORTE}`} style={{ fontSize: "15.5px", fontWeight: 750 }}>
            <span className={`grid place-items-center w-9 h-9 rounded-[10px] text-white ${BUSCA[busca].ponto}`}><Ic icon={icon} /></span>
            {titulo}
          </div>
          <Chave busca={busca} sufixo={etiqueta} />
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1.5 items-center">
          <span className={`uppercase tracking-[0.06em] mr-0.5 ${MUT}`} style={{ fontSize: "11px", fontWeight: 700 }}>Exemplo</span>
          {exemplos.map((e) => <Chip key={e} busca={busca}>{e}</Chip>)}
        </div>
        <FacaEvite faca={faca} evite={evite} />
        {children}
      </div>
    </div>
  );
}

function Etapa({ n, icon, titulo, selo, aviso, children }: {
  n: string; icon: LucideIcon; titulo: string; selo?: ReactNode; aviso?: boolean; children: ReactNode;
}) {
  const no = aviso ? "bg-[#A9781F] text-white" : "bg-gradient-to-br from-[#24507E] to-[#1A3A5C] text-white";
  const numero = aviso ? "text-[#A9781F] border-[#A9781F]" : "text-[#1A3A5C] border-[#1A3A5C] dark:text-[#8AB0DC] dark:border-[#8AB0DC]";
  return (
    <li className="relative pl-[58px] sm:pl-[66px] pb-9 last:pb-0">
      <span className={`absolute left-0 top-[-2px] grid place-items-center w-11 h-11 sm:w-12 sm:h-12 rounded-[14px] shadow-[0_0_0_6px_#F7F7F9,0_6px_14px_-6px_rgba(26,58,92,0.6)] dark:shadow-[0_0_0_6px_#0E0E11] ${no}`}>
        <Ic icon={icon} className="w-6 h-6" />
        <span className={`absolute -bottom-2 -right-2 min-w-[22px] h-[22px] px-1 rounded-full grid place-items-center bg-white dark:bg-[#17171B] border-2 ${numero}`} style={{ fontSize: "11.5px", fontWeight: 800 }}>{n}</span>
      </span>
      <div className="flex flex-wrap items-center gap-2.5 min-h-[44px]">
        <h2 className={NAVY_TXT} style={{ fontSize: "21px", fontWeight: 750, letterSpacing: "-0.015em" }}>{titulo}</h2>
        {selo}
      </div>
      {children}
    </li>
  );
}

function Lead({ children }: { children: ReactNode }) {
  return <p className={`mt-1 mb-3.5 max-w-[660px] ${TXT}`} style={{ fontSize: "14.5px", lineHeight: 1.6 }}>{children}</p>;
}

const B = ({ children }: { children: ReactNode }) => <b className={FORTE} style={{ fontWeight: 700 }}>{children}</b>;

export function GuiaPage() {
  return (
    <div className="flex flex-col min-h-full bg-[#F7F7F9] dark:bg-[#0E0E11]">
      <header className="flex items-center pl-20 pr-4 sm:pr-8 py-4 sticky top-0 z-10 bg-[#F7F7F9] dark:bg-[#0E0E11]">
        <span className="text-[#C0C0CE] dark:text-[#5E5E6A] truncate" style={{ fontSize: "14.4px" }}>Guia de uso</span>
      </header>

      <div className="w-full max-w-[880px] mx-auto px-4 sm:px-8 pt-4 pb-14">
        {/* Topo */}
        <div className="text-center mb-6">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 uppercase tracking-[0.09em] ${QUADRADO_NAVY}`} style={{ fontSize: "11.5px", fontWeight: 700 }}>
            <Ic icon={BookOpen} className="w-3.5 h-3.5" />Guia de uso
          </span>
          <h1 className={`mt-3.5 mb-2 ${NAVY_TXT}`} style={{ fontSize: "clamp(25px, 4.5vw, 31px)", fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.15 }}>
            Como tirar o melhor do JuriSight
          </h1>
          <p className={`mx-auto max-w-[580px] ${TXT}`} style={{ fontSize: "15px", lineHeight: 1.55 }}>
            Em cinco minutos: <b className={NAVY_TXT}>o caminho de uma busca</b>, <b className={NAVY_TXT}>o que cada campo da Revisão faz</b> e{" "}
            <b className={NAVY_TXT}>como ajustar</b> para achar a jurisprudência certa mais rápido.
          </p>
        </div>

        {/* Índice rápido */}
        <nav aria-label="Resumo do caminho" className="flex flex-wrap justify-center items-center gap-x-2 gap-y-1.5 mb-6">
          {[["1", "Conte o caso"], ["2–3", "Revise os campos"], ["4", "Filtre se precisar"], ["5–6", "Leia os resultados"]].map(([n, t], i, arr) => (
            <span key={n} className="inline-flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded-full pl-1.5 pr-3 py-1.5 bg-white dark:bg-[#17171B] border border-[#DCE6F3] dark:border-[#2A3A4C] ${NAVY_TXT}`} style={{ fontSize: "13px", fontWeight: 600 }}>
                <span className="rounded-full px-1.5 py-[1px] bg-[#EEF3FA] dark:bg-[#1A2A3C]" style={{ fontSize: "11.5px", fontWeight: 800 }}>{n}</span>{t}
              </span>
              {i < arr.length - 1 && <Ic icon={ArrowRight} className="w-3.5 h-3.5 text-[#9AAAC0]" />}
            </span>
          ))}
        </nav>

        {/* Acervo */}
        <section aria-label="O que o acervo cobre" className="relative overflow-hidden grid grid-cols-[auto_1fr] gap-4 sm:gap-[18px] items-center rounded-2xl px-5 py-5 mb-10 text-white bg-gradient-to-br from-[#1A3A5C] to-[#1F4670] shadow-[0_10px_24px_-12px_rgba(26,58,92,0.55)]">
          <span className="grid place-items-center w-[54px] h-[54px] rounded-[14px] bg-white text-[#1A3A5C]"><Ic icon={Database} className="w-6 h-6" /></span>
          <div className="min-w-0">
            <div className="uppercase tracking-[0.08em] text-[#B9CDE6]" style={{ fontSize: "11.5px", fontWeight: 700 }}>Antes de começar · o que o acervo cobre</div>
            <div className="mt-0.5" style={{ fontSize: "15.5px" }}>
              <b className="text-white mr-1" style={{ fontSize: "30px", fontWeight: 800, letterSpacing: "-0.02em" }}>{ACERVO}</b>
              acórdãos trabalhistas — é tudo que a busca enxerga.
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {([[Calendar, "96% julgados em 2025"], [Clock, "abr/2024 → mai/2026"], [Landmark, "25 tribunais"], [Ban, "Sem súmulas, OJs ou sentenças"]] as const).map(([icon, t]) => (
                <span key={t} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 bg-white/12 border border-white/20" style={{ fontSize: "12.5px", fontWeight: 600 }}>
                  <Ic icon={icon} className="w-3.5 h-3.5" />{t}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Trilha */}
        <ol aria-label="Etapas" className="relative before:content-[''] before:absolute before:left-[21px] sm:before:left-[23px] before:top-6 before:bottom-6 before:w-0.5 before:bg-[repeating-linear-gradient(#DCE6F3_0_6px,transparent_6px_11px)] dark:before:bg-[repeating-linear-gradient(#2A3A4C_0_6px,transparent_6px_11px)]">
          <Etapa n="1" icon={FileText} titulo="Conte o caso">
            <Lead>Na tela inicial, envie o <B>PDF</B> da petição ou do processo, ou <B>escreva</B> em poucas linhas o que quer sustentar. Os dois juntos funcionam melhor.</Lead>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Mini icon={Upload} titulo="PDF">A IA lê o texto e tira dele o pedido, os fatos e as normas citadas.</Mini>
              <Mini icon={MessageSquare} titulo="Texto">Diga o pedido e os fatos principais: <i>“gestante dispensada no 3º mês; empresa diz que não sabia”</i>.</Mini>
            </div>
            <Nota icon={ShieldCheck} tom="navy"><b>Seu documento fica aqui.</b> O PDF é lido pela IA do próprio JuriSight; para fora vão só os campos revisados e ementas públicas.</Nota>
          </Etapa>

          <Etapa n="2" icon={Sparkles} titulo="A IA monta a Revisão de Contexto">
            <Lead>Em segundos, o caso vira <B>campos organizados</B>. A IA não inventa de propósito, mas <B>pode errar ou deixar campos vazios</B> — por isso o próximo passo é seu.</Lead>
          </Etapa>

          <Etapa
            n="3" icon={PencilLine} titulo="Revise os campos"
            selo={<span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 uppercase tracking-[0.05em] ${QUADRADO_NAVY}`} style={{ fontSize: "11px", fontWeight: 700 }}><Ic icon={Star} className="w-3.5 h-3.5 text-[#F2C94C]" />O passo que mais muda o resultado</span>}
          >
            <Lead>
              Cada campo alimenta um jeito de buscar, e a cor mostra qual:{" "}
              <Chave busca="termos" /> procura as <B>palavras exatas</B> ·{" "}
              <Chave busca="semantica" /> procura <B>o mesmo sentido</B>, com outras palavras.
            </Lead>
            <div className="flex flex-col gap-3">
              <Campo busca="termos" icon={Target} titulo="Pedido principal" exemplos={["estabilidade da gestante"]}
                faca="O nome do instituto, como aparece em ementa" evite="Uma frase longa contando o caso" />
              <Campo busca="termos" icon={List} titulo="Fatos do caso" exemplos={["gravidez", "dispensa sem justa causa"]}
                faca="Um fato curto por item" evite="Datas, nomes e valores — não ajudam a achar decisões" />
              <Campo busca="termos" icon={Building2} titulo="Condutas da empresa" exemplos={["não reintegrou a empregada"]}
                faca="O que a empresa fez ou deixou de fazer" evite="Repetir o que já está nos fatos" />
              <Campo busca="semantica" icon={Quote} titulo="Tese central" etiqueta=" + ordem final"
                exemplos={["“A estabilidade da gestante independe da ciência do empregador sobre a gravidez.”"]}
                faca="Uma frase completa, no tom de uma ementa" evite="Palavras soltas: “gestante estabilidade”">
                <Nota icon={Star} tom="semantica"><b>O campo mais importante.</b> Além de buscar, ele decide <b>a ordem</b> das 20 decisões mostradas.</Nota>
              </Campo>
            </div>
          </Etapa>

          <Etapa
            n="4" icon={Filter} titulo="Use o filtro restrito"
            selo={<span className={`inline-flex rounded-full px-2.5 py-1 uppercase tracking-[0.05em] border-[1.5px] border-[#1A3A5C] dark:border-[#8AB0DC] ${NAVY_TXT}`} style={{ fontSize: "11px", fontWeight: 700 }}>Opcional · só se precisar</span>}
          >
            <Lead>Aqui você <B>exige</B>: só entram decisões que cumprem <B>tudo</B> o que estiver no filtro. Ótimo para ir ao nicho — mas <B>cada exigência corta o acervo</B>.</Lead>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Mini icon={Scale} titulo="Normas e dispositivos">
                Escolha da lista: art. 10 do ADCT, NR-15, Tema 1046…
                <div className="flex flex-wrap gap-1.5 mt-2"><Chip busca="filtro">ADCT art. 10, II, b</Chip><Chip tracejado>lei estadual 123</Chip></div>
                <div className={`mt-1.5 ${MUT}`} style={{ fontSize: "12.5px" }}><B>Sólido</B> filtra. <B>Tracejado</B> (fora da lista) só ajuda a busca por termos.</div>
              </Mini>
              <Mini icon={Type} titulo="Expressões obrigatórias">
                O texto que a decisão <B>tem</B> de conter. Aceita plural e falta de acento.
                <div className="flex flex-wrap gap-1.5 mt-2"><Chip busca="filtro">dano moral coletivo</Chip></div>
              </Mini>
              <Mini icon={Landmark} titulo="Tribunal">Um ou mais. Entre eles vale <B>“ou”</B>: TRT-4 <i>ou</i> TRT-12.</Mini>
              <Mini icon={Layers} titulo="Fase do processo"><B>Conhecimento</B> (recursos ordinários) ou <B>Execução</B> (agravos de petição, que discutem cálculo).</Mini>
            </div>
            <Nota icon={Hash} tom="navy">Acompanhe o contador <b>“Com todos os filtros: N decisões”</b>. Ficou baixo? Tire uma exigência — a expressão obrigatória costuma ser a mais restritiva.</Nota>
          </Etapa>

          <Etapa n="5" icon={Route} titulo="O que acontece quando você busca">
            <Lead>De <B>69 mil</B> decisões até as <B>20</B> que aparecem na tela, em três etapas.</Lead>
            <Funil />
          </Etapa>

          <Etapa n="6" icon={ChartNoAxesColumn} titulo="Leia os resultados">
            <Lead>No topo, um painel mostra <B>exatamente como a busca foi feita</B> — nas mesmas cores deste guia.</Lead>
            <div className="rounded-2xl px-4 py-3.5 text-[#EEF3FA] bg-gradient-to-b from-[#1A3A5C] to-[#1F4670]" style={{ fontSize: "13px" }}>
              <div className="flex items-center gap-2 text-white" style={{ fontSize: "14px", fontWeight: 700 }}><Ic icon={Info} className="w-4 h-4" />Como esta busca foi feita</div>
              <div className="flex flex-wrap gap-2.5 mt-2.5">
                {(["filtro", "semantica", "termos"] as const).map((b) => (
                  <span key={b} className="inline-flex items-center gap-2 rounded-lg px-2.5 py-1 bg-white/8 text-[#D7E3F3]" style={{ fontWeight: 600 }}>
                    <span className={`w-2.5 h-2.5 rounded-[3px] ${BUSCA[b].pontoSobreMarinho}`} />
                    {BUSCA[b].nome}{b === "filtro" && <> · <b className="text-white">1.104</b> de {ACERVO}</>}
                  </span>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              <Mini icon={Sparkles} titulo="Resposta da IA">Um resumo do que as decisões dizem, citando cada uma. <B>Abra a decisão antes de citar.</B></Mini>
              <Mini icon={Layers} titulo="Busca livre">Com filtro, as decisões que não passaram nele ficam numa faixa à parte, que você abre se quiser.</Mini>
            </div>
            <Nota icon={PencilLine} tom="neutro"><B>Não achou?</B> Clique no <B>lápis</B> ao lado de “Revisão de contexto”, ajuste e busque de novo — cada ajuste vira uma nova versão da conversa.</Nota>
          </Etapa>

          <Etapa
            n="!" icon={AlertTriangle} titulo="Limites desta versão" aviso
            selo={<span className="inline-flex rounded-full px-2.5 py-1 uppercase tracking-[0.05em] bg-[#FBF4E4] dark:bg-[#2A2312] text-[#7A5410] dark:text-[#D9B36A] border-[1.5px] border-[#E3C88E] dark:border-[#5A4720]" style={{ fontSize: "11px", fontWeight: 700 }}>MVP</span>}
          >
            <Lead>O JuriSight é um protótipo de TCC. Use como <B>ponto de partida</B> da pesquisa, não como pesquisa completa.</Lead>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {([
                [Database, "Acervo pequeno", "69 mil acórdãos, quase todos de 2025. Se não aparece, pode simplesmente não estar no acervo."],
                [FileText, "Só acórdãos", "Súmulas, OJs e sentenças não entram na busca — só aparecem citadas dentro das decisões."],
                [Sparkles, "A IA pode errar", "Na extração dos campos, no resumo e na indicação de favorável/desfavorável."],
                [BookOpen, "Não substitui a leitura", "Confira a decisão inteira antes de usá-la numa peça."],
              ] as const).map(([icon, t, d]) => (
                <div key={t} className={`${CARD} flex gap-3 items-start p-4 border-l-4 border-l-[#A9781F] ${TXT}`} style={{ fontSize: "13.5px", lineHeight: 1.5 }}>
                  <span className="grid place-items-center w-9 h-9 rounded-[10px] flex-none bg-[#FBF4E4] dark:bg-[#2A2312] text-[#A9781F] dark:text-[#D9B36A]"><Ic icon={icon} /></span>
                  <div><span className={`block mb-0.5 ${FORTE}`} style={{ fontSize: "14.5px", fontWeight: 750 }}>{t}</span>{d}</div>
                </div>
              ))}
            </div>
          </Etapa>
        </ol>

        {/* Chamada final */}
        <div className={`${CARD} mt-10 flex flex-wrap justify-between items-center gap-4 px-5 py-5`}>
          <div>
            <div className={NAVY_TXT} style={{ fontSize: "17px", fontWeight: 800, letterSpacing: "-0.01em" }}>Pronto para a primeira busca?</div>
            <div className={`mt-0.5 ${TXT}`} style={{ fontSize: "13.5px" }}>Comece pela tela inicial — envie o PDF ou conte o caso.</div>
          </div>
          <Link href="/" className="inline-flex items-center gap-2 rounded-[11px] px-[18px] py-[11px] bg-[#1A3A5C] hover:bg-[#24507E] text-white transition-colors dark:bg-[#8AB0DC] dark:hover:bg-[#A4C2E4] dark:text-[#0E0E11]" style={{ fontSize: "14px", fontWeight: 700 }}>
            Ir para a tela inicial<Ic icon={ArrowRight} className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

function Seta() {
  return <div className="grid place-items-center h-[22px] text-[#1A3A5C]/45 dark:text-[#8AB0DC]/45"><Ic icon={ArrowDown} className="w-4 h-4" /></div>;
}

function Funil() {
  const desc = `${TXT}`;
  const tt = (cor: string, t: string) => <span className={`block ${cor}`} style={{ fontSize: "14.5px", fontWeight: 750 }}>{t}</span>;
  return (
    <div className="flex flex-col items-center" style={{ fontSize: "13.5px", lineHeight: 1.45 }}>
      <div className="w-full flex items-center gap-3 rounded-2xl px-4 py-3 bg-[#1A3A5C] text-white">
        <span className="grid place-items-center w-[38px] h-[38px] rounded-[10px] bg-white text-[#1A3A5C]"><Ic icon={Database} /></span>
        <div className="text-[#C9D8EC]">{tt("text-white", "Acervo inteiro")}todos os acórdãos</div>
        <span className="ml-auto tabular-nums" style={{ fontSize: "24px", fontWeight: 800 }}>{ACERVO}</span>
      </div>
      <Seta />
      <div className="w-full sm:w-[92%] flex items-center gap-3 rounded-2xl px-4 py-3 bg-white dark:bg-[#17171B] border-2 border-[#1A3A5C] dark:border-[#8AB0DC]">
        <span className={`grid place-items-center w-[38px] h-[38px] rounded-[10px] flex-none ${QUADRADO_NAVY}`}><Ic icon={Filter} /></span>
        <div className={desc}>{tt(FORTE, `1 · ${BUSCA.filtro.nome}`)}se você usou, só passa quem cumpre tudo · ex.: TRT-4 + Conhecimento</div>
        <span className={`ml-auto tabular-nums ${NAVY_TXT}`} style={{ fontSize: "24px", fontWeight: 800 }}>3.796</span>
      </div>
      <Seta />
      <div className="w-full sm:w-[84%] grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {(["semantica", "termos"] as const).map((b) => (
          <div key={b} className={`flex items-center gap-3 rounded-2xl px-4 py-3 border-[1.5px] ${BUSCA[b].chip}`}>
            <span className={`grid place-items-center w-[38px] h-[38px] rounded-[10px] flex-none text-white ${BUSCA[b].ponto}`}><Ic icon={ICONE_BUSCA[b]} /></span>
            <div>
              <span className="block" style={{ fontSize: "14.5px", fontWeight: 750 }}>2 · {BUSCA[b].nome}</span>
              <span className={desc}>{b === "semantica" ? "sentido mais próximo da tese" : "mais palavras em comum"}</span>
            </div>
          </div>
        ))}
      </div>
      <Seta />
      <div className={`${CARD} w-full sm:w-[76%] flex items-center gap-3 px-4 py-3`}>
        <span className={`grid place-items-center w-[38px] h-[38px] rounded-[10px] flex-none ${QUADRADO_NAVY}`}><Ic icon={ArrowDownWideNarrow} /></span>
        <div className={desc}>{tt(FORTE, "3 · Reordenação")}relidas contra a tese; a mais aderente primeiro</div>
        <span className={`ml-auto tabular-nums ${NAVY_TXT}`} style={{ fontSize: "24px", fontWeight: 800 }}>20</span>
      </div>
    </div>
  );
}
