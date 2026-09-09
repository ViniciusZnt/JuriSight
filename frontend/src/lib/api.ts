/** Cliente HTTP para o backend FastAPI (query/api/app.py). Fetch puro — sem lib
 *  externa. Tipos espelham os modelos Pydantic reais (EstruturaArgumentativa,
 *  ResultCard, DocumentoDetalhe). */

export interface EstruturaArgumentativa {
  pedido_principal: string;
  agente_nocivo: string[];
  violacoes: string[];
  normas: string[];
  empresa_ciente: boolean | null;
  setor: string | null;
  cargo: string | null;
  tese_central: string;
}

export type TipoDocumento = "ACORDAO" | "SUMULA" | "OJ" | "PRECEDENTE";
export type Provimento = "APROVADO" | "PARCIAL" | "NEGADO" | "NAO_APLICAVEL";

export interface ResultCard {
  id: string;
  tipo_documento: TipoDocumento;
  hierarquia_categoria: number;
  numero_processo: string;
  tribunal: string;
  turma: string;
  relator: string;
  data_julgamento: string | null;
  ementa: string;
  provimento: Provimento;
  link_original: string | null;
  score_rrf: number;
}

export interface DocumentoDetalhe extends ResultCard {
  classe_processo: string;
  sigla_classe: string;
  gabinete: string;
  cabecalho: string;
  relatorio: string;
  fundamentacao: string;
  acordao: string;
  votos: string;
  referencia_legislativa: string[];
}

export interface EnrichResponse {
  estrutura: EstruturaArgumentativa;
  /** null = nenhum PDF enviado (FA01) · true = extraído com sucesso · false = FA02. */
  pdf_extraido: boolean | null;
  aviso: string | null;
}

export interface QueryBody {
  estrutura: EstruturaArgumentativa;
  provimento?: Provimento;
  data_inicio?: string;
  data_fim?: string;
  ordenar_por?: "relevancia" | "data";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Erro de resposta HTTP (4xx/5xx) do backend — carrega o status e a mensagem
 *  (`detail`, quando o corpo é JSON) para a página decidir como exibir. Erros
 *  de rede (backend fora do ar) propagam como o TypeError nativo do fetch. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* corpo não é JSON — usa o texto padrão do status */
  }
  return `Erro ${res.status} ao chamar a API.`;
}

/** RF02/RF03/FA01/FA02 — extrai a EstruturaArgumentativa do PDF e/ou da intenção. */
export async function enrich(params: { pdf?: File; intencao?: string }): Promise<EnrichResponse> {
  const form = new FormData();
  if (params.pdf) form.append("pdf", params.pdf);
  if (params.intencao) form.append("intencao", params.intencao);

  const res = await fetch(`${API_URL}/enrich`, { method: "POST", body: form });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return res.json();
}

/** RF04/RF07/RN02 — busca híbrida sobre a EstruturaArgumentativa revisada. */
export async function query(body: QueryBody): Promise<ResultCard[]> {
  const res = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return res.json();
}

/** RF08 — detalhe completo de um documento. */
export async function getDocument(id: string): Promise<DocumentoDetalhe> {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(id)}`);
  if (!res.ok) throw new ApiError(res.status, await parseErrorDetail(res));
  return res.json();
}
