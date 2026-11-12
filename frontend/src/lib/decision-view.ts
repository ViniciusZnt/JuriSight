import { rotuloTribunal, type EstruturaArgumentativa, type ResultCard, type TipoDocumento } from "@/lib/api";

const GENERICO = /^(ementa|direito (processual )?do trabalho( e processual do trabalho)?|recurso ordin[áa]rio( trabalhista)?)$/i;

/** O schema real não tem um campo de "título" — a ementa é o único texto de manchete. Usa a
 *  verbetação do começo (os temas em caixa alta: "ADICIONAL DE INSALUBRIDADE. RUÍDO. EPI."), sem os
 *  genéricos que quase toda ementa repete ("DIREITO DO TRABALHO. RECURSO ORDINÁRIO."), para os
 *  cards não ficarem com o mesmo título; sem verbetação, a primeira frase. */
export function titleFromEmenta(ementa: string): string {
  const trimmed = ementa.trim().replace(/^ementa\s*:?\s*/i, "");
  if (!trimmed) return "Decisão sem ementa disponível";
  const temas: string[] = [];
  for (const seg of trimmed.split(/\.\s+|\s+[-–—]\s+/)) {
    const t = seg.trim().replace(/\.$/, "");
    const minusculas = t.match(/\p{Ll}/gu)?.length ?? 0;
    if (!t || minusculas > t.length * 0.2 || /^([IVX]+|\d+)$|CASO EM EXAME/.test(t)) break;
    if (GENERICO.test(t)) continue;
    if (temas.length && `${temas.join(". ")}. ${t}`.length > 100) break;
    temas.push(t);
  }
  const titulo = temas.length ? `${temas.join(". ")}.` : (trimmed.split(/(?<=[.!?])\s/)[0] ?? trimmed);
  return titulo.length > 140 ? `${titulo.slice(0, 140).replace(/\s+\S*$/, "")}…` : titulo;
}

/** Ementa praticamente igual à de um resultado mais bem posicionado (mesmas palavras em ≥ 90%,
 *  Jaccard): id → id do primeiro, para o card avisar "ementa igual à de #k". Recebe em ordem de relevância. */
export function ementasRepetidas(porRelevancia: { id: string; ementa: string }[]): Map<string, string> {
  const palavras = porRelevancia.map((d) => new Set(d.ementa.toLowerCase().match(/[\p{L}\d]{3,}/gu) ?? []));
  const out = new Map<string, string>();
  porRelevancia.forEach((d, i) => {
    const a = palavras[i];
    for (let j = 0; j < i && a.size > 0; j++) {
      const b = palavras[j];
      let comum = 0;
      a.forEach((w) => (comum += b.has(w) ? 1 : 0));
      if (comum / (a.size + b.size - comum) >= 0.9) {
        out.set(d.id, porRelevancia[j].id);
        break;
      }
    }
  });
  return out;
}

/** Data ISO (yyyy-mm-dd) no fuso local — `new Date("2025-12-17")` seria meia-noite UTC e viraria 16/12 no Brasil. */
export function formatarData(iso: string | null, mes: "2-digit" | "short" | "long" = "2-digit"): string {
  return iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: mes, year: "numeric" })
    : "Data não informada";
}

type Citavel = Pick<ResultCard, "ementa" | "tribunal" | "turma" | "numero_processo" | "data_julgamento" | "relator">;

/** "TRT2, 11ª Turma, Processo 0001, julgado em 17/12/2025, Rel. Fulana". */
export function citacaoDe(d: Omit<Citavel, "ementa">): string {
  return [
    `${d.tribunal}, ${d.turma}`,
    `Processo ${d.numero_processo}`,
    d.data_julgamento && `julgado em ${formatarData(d.data_julgamento)}`,
    d.relator && `Rel. ${d.relator}`,
  ]
    .filter(Boolean)
    .join(", ");
}

/** Ementa + linha de citação (tribunal, turma, processo, data, relator), para colar numa peça. */
export function ementaComCitacao(d: Citavel): string {
  return `${d.ementa.trim()}\n\n(${citacaoDe(d)}.)`;
}

/** Título do card: classe, identificação e data antes da verbetação, para cards de mesmo tema (e até
 *  de ementa igual, da mesma turma) não ficarem iguais ("RORSum · TRT2 · 11ª Turma · 12/05/2025 — ADICIONAL…"). */
// Siglas que continuam em maiúsculas quando o assunto da ementa vira frase.
const SIGLAS = new Set(["CLT", "TST", "STF", "STJ", "TRT", "TRF", "CF", "CPC", "CC", "ADCT", "OJ", "SDI", "SBDI", "EPI", "EPIS", "NR", "FGTS", "CTPS", "INSS", "PLR", "PPP", "LTCAT", "CIPA", "MPT", "ACP", "RPV", "CTVA", "COVID", "LGPD", "CNH", "PJE", "IRDR", "IAC", "ROT", "RORSUM", "AP", "AIRR", "RR"]);
const ROMANO = /^[IVXLC]+$/;

/** Assunto da ementa para o título do card: o que está todo em maiúsculas ("MOTORISTA
 *  PROFISSIONAL. HORAS EXTRAS.") vira frase ("Motorista profissional. Horas extras."), com as
 *  siglas e os números romanos preservados; texto que já tem minúsculas fica como está. */
export function assuntoDoCard(assunto: string): string {
  if (/\p{Ll}/u.test(assunto)) return assunto;
  const palavras = assunto.split(/(\s+)/).map((p) => {
    const nucleo = p.replace(/[^\p{L}\d-]/gu, "");
    const base = nucleo.split("-")[0];
    if (SIGLAS.has(base) || (ROMANO.test(nucleo) && nucleo.length <= 4)) return p;
    return p.toLocaleLowerCase("pt-BR");
  });
  let frase = palavras.join("");
  // maiúscula no começo e depois de cada ponto
  frase = frase.replace(/(^|[.!?]\s+)(\p{Ll})/gu, (_, antes: string, letra: string) => antes + letra.toLocaleUpperCase("pt-BR"));
  return frase;
}

export function tituloDoCard(d: Pick<ResultCard, "ementa" | "tribunal" | "turma" | "sigla_classe" | "data_julgamento">): string {
  const data = d.data_julgamento && formatarData(d.data_julgamento);
  const id = [d.sigla_classe, d.tribunal, d.turma, data].filter(Boolean).join(" · ");
  return id ? `${id} — ${titleFromEmenta(d.ementa)}` : titleFromEmenta(d.ementa);
}

/** Itens de uma frase-lista da resposta ("a; b; c"), para mostrar como lista. Com `semPrefixo`,
 *  tira o começo até o primeiro ":" ("Para o pedido, é preciso provar: …"). Cada item começa com
 *  maiúscula e sem ponto final. */
export function itensDaFrase(texto: string, semPrefixo = false): string[] {
  const corpo = semPrefixo && texto.includes(":") ? texto.slice(texto.indexOf(":") + 1) : texto;
  return corpo
    .split(";")
    .map((i) => i.trim().replace(/\.$/, ""))
    .filter(Boolean)
    .map((i) => i[0].toUpperCase() + i.slice(1));
}

/** "CLT art. 189: se …" → ["CLT art. 189", "Se …"], para o dispositivo vir em negrito; sem ":", [null, item]. */
export function dispositivoETexto(item: string): [string | null, string] {
  const i = item.indexOf(":");
  if (i <= 0) return [null, item];
  const resto = item.slice(i + 1).trim();
  return [item.slice(0, i).trim(), resto && resto[0].toUpperCase() + resto.slice(1)];
}

/** Resposta gerada em texto para colar numa peça: cada frase com "[1, 3]" e, no fim, a citação
 *  completa de cada decisão citada. `porNumero`: número do card -> decisão. */
export function respostaParaCopiar(
  frases: { texto: string; citacoes: number[] }[],
  porNumero: Map<number, Omit<Citavel, "ementa">>
): string {
  const citadas = [...new Set(frases.flatMap((f) => f.citacoes))].sort((a, b) => a - b);
  const corpo = frases.map((f) => (f.citacoes.length ? `${f.texto} [${f.citacoes.join(", ")}]` : f.texto)).join(" ");
  const fontes = citadas.filter((n) => porNumero.has(n)).map((n) => `[${n}] ${citacaoDe(porNumero.get(n)!)}.`);
  return `${corpo}\n\nDecisões citadas:\n${fontes.join("\n")}`;
}

export function truncate(text: string, max: number): string {
  const trimmed = text.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max).trimEnd()}…` : trimmed;
}

/** "Entidades correspondentes": termos do contexto pesquisado (normas/agentes/violações) que
 *  aparecem literalmente no texto do documento. A API não devolve spans/highlights, então esta
 *  é a única checagem honesta possível no cliente — sem inventar uma correspondência que o
 *  backend não calculou. */
export function matchedEntities(estrutura: EstruturaArgumentativa | null, texto: string): string[] {
  if (!estrutura) return [];
  const haystack = texto.toLowerCase();
  const candidatos = [...estrutura.normas, ...estrutura.agente_nocivo, ...estrutura.violacoes];
  const vistos = new Set<string>();
  return candidatos.filter((termo) => {
    const t = termo.trim();
    if (!t || vistos.has(t.toLowerCase())) return false;
    if (!haystack.includes(t.toLowerCase())) return false;
    vistos.add(t.toLowerCase());
    return true;
  });
}

/** Posição de cada resultado na ordem de relevância da busca (1 = mais relevante). O score vem
 *  normalizado só dentro do lote (query/search/pipeline.py), sem escala absoluta — um "%"
 *  repetia 100% em vários cards; a posição é o que o score de fato informa. */
export function relevanceRanks(results: { id: string; score_rrf: number }[]): Map<string, number> {
  const ordem = [...results].sort((a, b) => b.score_rrf - a.score_rrf);
  return new Map(ordem.map((r, i) => [r.id, i + 1]));
}

/** Reordena no cliente o mesmo lote de resultados, sem chamar a API de novo — hierarquia
 *  jurídica primeiro (súmula > OJ > precedente > acórdão), relevância/data como critério secundário. */
export function compareResultCards(a: ResultCard, b: ResultCard, por: "relevancia" | "data"): number {
  if (a.hierarquia_categoria !== b.hierarquia_categoria) {
    return a.hierarquia_categoria - b.hierarquia_categoria;
  }
  if (por === "data") {
    const da = a.data_julgamento ? Date.parse(a.data_julgamento) : -Infinity;
    const db = b.data_julgamento ? Date.parse(b.data_julgamento) : -Infinity;
    return db - da;
  }
  return b.score_rrf - a.score_rrf;
}

export const TIPO_DOCUMENTO_LABEL: Record<TipoDocumento, string> = {
  ACORDAO: "Acórdão",
  SUMULA: "Súmula",
  OJ: "Orientação Jurisprudencial",
  PRECEDENTE: "Precedente",
};

/** Parágrafos de um texto do documento: usa as quebras do original; sem elas (o inteiro teor vem
 *  numa linha só), quebra antes de itens numerados ("1. Recurso…", "II. QUESTÃO…"). */
export function paragrafos(texto: string): string[] {
  const t = texto.trim();
  const partes = t.includes("\n\n") ? t.split(/\n\s*\n/) : t.split(/\s(?=(?:[IVX]{1,4}|\d{1,2})\.\s+\p{Lu})/u);
  return partes.map((p) => p.trim()).filter(Boolean);
}

/** O campo `acordao` traz o inteiro teor; o dispositivo é o trecho a partir do último "ACORDAM"
 *  (ou do último "Ante/Diante do exposto", "Isto posto", "Posto isso"), cortado numa frase. */
export function dispositivoDe(teor: string, max = 1500): string | null {
  const ultimo = (re: RegExp) => [...teor.matchAll(re)].pop()?.index;
  const i = ultimo(/\bacordam\b/gi) ?? ultimo(/\b(?:ante|diante) do exposto|\bisto posto|\bposto isso/gi);
  if (i === undefined) return null;
  const trecho = teor.slice(i, i + max).trim();
  if (teor.length - i <= max) return trecho;
  const fim = trecho.lastIndexOf(". ");
  return `${fim > 0 ? trecho.slice(0, fim + 1) : trecho} […]`;
}


// Ordinais por extenso nas turmas ("Quarta Turma", "Décima Primeira Turma").
const ORDINAIS: Record<string, number> = {
  primeira: 1, segunda: 2, terceira: 3, quarta: 4, quinta: 5, sexta: 6, setima: 7, oitava: 8, nona: 9,
  decima: 10, vigesima: 20,
};
const semAcento = (t: string) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

/** Órgão no padrão de citação: "1ª Turma do TRT-4" (turma por extenso, com zero à esquerda ou em
 *  maiúsculas vira "4ª Turma"; câmaras e seções seguem o mesmo jeito; sem turma, só o tribunal). */
export function orgaoDe(d: Pick<ResultCard, "tribunal" | "turma">): string {
  const tribunal = rotuloTribunal(d.tribunal);
  const bruto = d.turma.trim();
  if (!bruto) return tribunal;
  const palavras = bruto.split(/\s+/);
  let n = 0;
  let i = 0;
  for (; i < palavras.length; i++) {
    const v = ORDINAIS[semAcento(palavras[i].toLowerCase())];
    if (v === undefined) break;
    n += v;
  }
  let orgao: string;
  if (n > 0) orgao = `${n}ª ${palavras.slice(i).join(" ")}`;
  else orgao = bruto.replace(/^0+(\d)/, "$1");
  // "3ª TURMA" → "3ª Turma"
  orgao = orgao.replace(/\p{Lu}{2,}/gu, (w) => w.charAt(0) + w.slice(1).toLocaleLowerCase("pt-BR"));
  return `${orgao} do ${tribunal}`;
}

/** Órgãos das decisões citadas por uma frase, sem repetir: "1ª Turma do TRT-4 e 2ª Turma do
 *  TRT-22"; acima de dois, "…, … e mais N". */
export function orgaosCitados(decisoes: Pick<ResultCard, "tribunal" | "turma">[]): string {
  const unicos = [...new Set(decisoes.map(orgaoDe))];
  if (unicos.length <= 2) return unicos.join(" e ");
  return `${unicos.slice(0, 2).join(", ")} e mais ${unicos.length - 2}`;
}

/** Separa o veredito ("Sim", "Não", "Depende") do começo da resposta. Depois de "." ou "," o resto
 *  vira frase com maiúscula; "Depende de …" continua a mesma frase. */
export function vereditoDe(texto: string): { veredito: "Sim" | "Não" | "Depende" | null; resto: string } {
  const m = texto.trim().match(/^(sim|não|nao|depende)\b\s*([.,:;—-])?\s*/i);
  if (!m) return { veredito: null, resto: texto.trim() };
  const palavra = m[1].toLowerCase();
  const veredito = palavra === "sim" ? "Sim" : palavra === "depende" ? "Depende" : "Não";
  const resto = texto.trim().slice(m[0].length);
  return { veredito, resto: m[2] ? resto.charAt(0).toLocaleUpperCase("pt-BR") + resto.slice(1) : resto };
}
