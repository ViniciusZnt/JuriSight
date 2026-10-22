/** Cliente HTTP da API FastAPI (query/api/app.py). Único ponto do frontend que fala com o
 *  backend — tipos aqui espelham os schemas Pydantic (EstruturaArgumentativa, ResultCard,
 *  DocumentoDetalhe) para o contrato ficar num só lugar. */

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type TipoDocumento = "ACORDAO" | "SUMULA" | "OJ" | "PRECEDENTE";
export type Provimento = "APROVADO" | "PARCIAL" | "NEGADO" | "NAO_APLICAVEL";

/** query/enrichment/schema.py::EstruturaArgumentativa — todo campo tem default (RN05: o LLM
 *  nunca inventa; o que não foi encontrado no texto fica vazio/null). */
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

export function emptyEstrutura(): EstruturaArgumentativa {
  return {
    pedido_principal: "",
    agente_nocivo: [],
    violacoes: [],
    normas: [],
    empresa_ciente: null,
    setor: null,
    cargo: null,
    tese_central: "",
  };
}

export interface EnrichResponse {
  estrutura: EstruturaArgumentativa;
  /** null = nenhum PDF enviado; true = extraído com sucesso; false = FA02 (PDF sem texto). */
  pdf_extraido: boolean | null;
  aviso: string | null;
}

/** query/search/result_formatter.py::ResultCard — card devolvido por POST /query. */
export interface ResultCard {
  id: string;
  tipo_documento: TipoDocumento;
  hierarquia_categoria: number;
  numero_processo: string;
  tribunal: string;
  turma: string;
  relator: string;
  data_julgamento: string | null; // ISO yyyy-mm-dd
  ementa: string;
  provimento: Provimento;
  link_original: string | null;
  score_rrf: number;
}

/** query/search/result_formatter.py::DocumentoDetalhe — DocumentoJuridico completo, devolvido
 *  por GET /document/{id}. Não tem score_rrf (isso é só do card de busca). */
export interface DocumentoDetalhe {
  id: string;
  id_documento: string;
  tipo_documento: TipoDocumento;
  hierarquia_categoria: number;
  data_filtro: string | null;
  numero_processo: string;
  tribunal: string;
  classe_processo: string;
  sigla_classe: string;
  relator: string;
  turma: string;
  gabinete: string;
  data_julgamento: string | null;
  data_juntada: string | null;
  cabecalho: string;
  ementa: string;
  relatorio: string;
  fundamentacao: string;
  acordao: string;
  votos: string;
  possui_ementa: boolean;
  referencia_legislativa: string[];
  provimento: Provimento;
  link_original: string | null;
}

export interface QueryRequestBody {
  estrutura: EstruturaArgumentativa;
  provimento?: Provimento | null;
  data_inicio?: string | null; // yyyy-mm-dd
  data_fim?: string | null;
}

/** Erro de API com o `detail` do FastAPI já extraído (HTTPException / 422 de validação). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function detailFrom(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      // Erro de validação do FastAPI/Pydantic (422): lista de {loc, msg}.
      return data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || `Erro ${res.status}.`;
    }
  } catch {
    /* corpo não é JSON — segue com a mensagem genérica */
  }
  return `Erro ${res.status} ao comunicar com a API.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    // credentials: "include" em toda chamada — necessário pro cookie httpOnly de
    // sessão (query/api/auth_routes.py) ir e voltar entre :3000 e :8000; inofensivo
    // nas rotas que não usam cookie.
    res = await fetch(`${API_BASE_URL}${path}`, { credentials: "include", ...init });
  } catch {
    throw new ApiError(
      "Não foi possível conectar à API. Verifique se o backend (FastAPI) está rodando.",
      0
    );
  }
  if (!res.ok) throw new ApiError(await detailFrom(res), res.status);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** POST /enrich — extrai a EstruturaArgumentativa do PDF e/ou da intenção digitada. Precisa de
 *  ao menos um dos dois (o backend responde 422 se ambos vierem vazios). */
export async function enrich(params: { pdf?: File | null; intencao?: string | null }): Promise<EnrichResponse> {
  const form = new FormData();
  if (params.pdf) form.append("pdf", params.pdf);
  if (params.intencao && params.intencao.trim()) form.append("intencao", params.intencao.trim());
  return request<EnrichResponse>("/enrich", { method: "POST", body: form });
}

/** POST /query — busca híbrida (RRF) sobre a EstruturaArgumentativa revisada. */
export async function queryJurisprudencia(body: QueryRequestBody): Promise<ResultCard[]> {
  return request<ResultCard[]>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** GET /document/{id} — detalhe completo de um documento (404 se não existir). */
export async function getDocument(id: string): Promise<DocumentoDetalhe> {
  return request<DocumentoDetalhe>(`/document/${encodeURIComponent(id)}`);
}

// --------------------------------------------------------------------------- //
// Autenticação (query/api/auth_routes.py) — sessão via cookie httpOnly, nunca   //
// um token no corpo/localStorage (ver o módulo do backend para o porquê).      //
// --------------------------------------------------------------------------- //

/** Campos públicos do usuário — nunca inclui a senha/hash. */
export interface UsuarioPublico {
  id: string;
  email: string;
  nome: string | null;
  is_active: boolean;
  criado_em: string;
}

/** POST /auth/registro — cria a conta. Não loga sozinho (não seta cookie); chame
 *  `loginUsuario` em seguida para entrar. */
export async function registrarUsuario(params: { email: string; password: string; nome?: string | null }): Promise<UsuarioPublico> {
  return request<UsuarioPublico>("/auth/registro", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/** POST /auth/login — o cookie de sessão é setado pelo backend na resposta; o
 *  token de acesso nunca aparece aqui. */
export async function loginUsuario(params: { email: string; password: string }): Promise<UsuarioPublico> {
  return request<UsuarioPublico>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/** POST /auth/logout — limpa o cookie de sessão no backend. */
export async function logoutUsuario(): Promise<void> {
  await request<void>("/auth/logout", { method: "POST" });
}

/** GET /auth/me — usuário da sessão atual a partir do cookie. Lança ApiError(401)
 *  se não houver sessão válida — use isso para checar se o usuário está logado. */
export async function getUsuarioAtual(): Promise<UsuarioPublico> {
  return request<UsuarioPublico>("/auth/me");
}

// --------------------------------------------------------------------------- //
// Conversas (query/api/conversa_routes.py) — histórico de busca persistido no  //
// Postgres, escopado ao usuário da sessão. Nunca inclui o PDF enviado nem seu  //
// texto — só a EstruturaArgumentativa revisada e os resultados do /query.     //
// --------------------------------------------------------------------------- //

/** query/api/conversa_routes.py::VersaoResponse — uma busca dentro de uma
 *  conversa ("V{numero}" no dropdown de versões). */
export interface VersaoApi {
  numero: number;
  estrutura: EstruturaArgumentativa;
  has_file: boolean;
  file_name: string | null;
  pdf_extraido: boolean | null;
  aviso: string | null;
  resultados: ResultCard[] | null;
  criado_em: string; // ISO datetime
}

/** query/api/conversa_routes.py::ConversaResponse. */
export interface ConversaApi {
  id: string;
  titulo: string;
  criado_em: string; // ISO datetime
  atualizado_em: string;
  versoes: VersaoApi[];
}

export interface NovaVersaoBody {
  estrutura: EstruturaArgumentativa;
  has_file: boolean;
  file_name?: string | null;
  pdf_extraido?: boolean | null;
  aviso?: string | null;
  resultados?: ResultCard[] | null;
}

/** GET /conversas — todas as conversas do usuário da sessão, mais recente primeiro. */
export async function listarConversas(): Promise<ConversaApi[]> {
  return request<ConversaApi[]>("/conversas");
}

/** POST /conversas — cria uma conversa nova, ainda sem snapshot. */
export async function criarConversa(titulo: string): Promise<ConversaApi> {
  return request<ConversaApi>("/conversas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
}

/** PATCH /conversas/{id} — renomeia. */
export async function renomearConversa(id: string, titulo: string): Promise<ConversaApi> {
  return request<ConversaApi>(`/conversas/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
}

/** DELETE /conversas/{id}. */
export async function apagarConversa(id: string): Promise<void> {
  await request<void>(`/conversas/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** POST /conversas/{id}/versoes — acrescenta uma versão nova (nunca sobrescreve as
 *  anteriores). Chamado toda vez que POST /query retorna com sucesso — a primeira busca
 *  vira V1, cada "Refinar consulta" bem-sucedido vira a próxima versão. Devolve a conversa
 *  inteira (todas as versões), pro dropdown V1/V2/... ficar completo sem outra chamada. */
export async function adicionarVersaoConversa(id: string, versao: NovaVersaoBody): Promise<ConversaApi> {
  return request<ConversaApi>(`/conversas/${encodeURIComponent(id)}/versoes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(versao),
  });
}
