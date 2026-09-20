"""
Query Enrichment (RFC Tabela 6/12) — LLM (Llama 3.2 3B via Ollama).

Extrai a EstruturaArgumentativa do texto do caso (PDF e/ou intenção argumentativa
digitada) via prompt few-shot com saída JSON estruturada (RF02). Componente
distinto do Query Builder (query_builder.py): aqui é a única etapa do pipeline
que chama um LLM para ENTENDER o caso; o Query Builder, depois, só monta strings
deterministicamente a partir do resultado.

RN05: o LLM é instruído a nunca alucinar — campos não encontrados no texto devem
vir null/lista vazia. A validação Pydantic de EstruturaArgumentativa (todo campo
com default) é a segunda camada de defesa disso.
"""
from __future__ import annotations

import os

import ollama

from query.enrichment.schema import EstruturaArgumentativa

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Exemplo few-shot — o próprio caso usado como exemplo na Tabela 10 da RFC, para
# manter o prompt consistente com o schema documentado.
_EXEMPLO_CASO = (
    "Reclamante trabalhou como operador de prensa no setor de metalurgia da "
    "empresa ré, exposto habitualmente a benzeno sem receber Equipamento de "
    "Proteção Individual eficaz. A empresa possuía PPRA e PCMSO que já "
    "identificavam o risco, mas não adotou medidas de proteção. Pede-se o "
    "pagamento de adicional de insalubridade em grau máximo, com base na NR-15 "
    "e no art. 192 da CLT."
)
_EXEMPLO_JSON = (
    '{"pedido_principal": "adicional de insalubridade grau máximo", '
    '"agente_nocivo": ["benzeno"], '
    '"violacoes": ["ausência de EPI eficaz"], '
    '"normas": ["NR-15", "CLT art. 192"], '
    '"empresa_ciente": true, '
    '"setor": "metalurgia", '
    '"cargo": "operador de prensa", '
    '"tese_central": "A empresa tinha ciência do risco e não forneceu proteção adequada."}'
)

_SYSTEM_PROMPT = f"""Você extrai a estrutura argumentativa de um caso trabalhista \
a partir do texto informado pelo advogado (PDF do processo e/ou a intenção \
argumentativa digitada).

Responda SEMPRE em JSON válido, com exatamente estes campos:
- pedido_principal (string): o que se pede na ação.
- agente_nocivo (lista de strings): agentes de risco citados (ex.: substâncias, ruído).
- violacoes (lista de strings): condutas omissivas ou comissivas da empresa.
- normas (lista de strings): normas jurídicas citadas (ex.: "NR-15", "CLT art. 192").
- empresa_ciente (true, false ou null): há evidência de que a empresa tinha ciência do risco?
- setor (string ou null): ramo de atividade da empresa.
- cargo (string ou null): cargo do trabalhador.
- tese_central (string): uma frase que resume o argumento principal do caso.

REGRAS IMPORTANTES:
- NUNCA invente informação que não esteja no texto.
- Se um campo não puder ser determinado a partir do texto, use null (para \
empresa_ciente/setor/cargo) ou lista vazia (para agente_nocivo/violacoes/normas). \
Não deixe de responder um campo — na dúvida, prefira null/lista vazia a adivinhar.

Exemplo:
Texto: {_EXEMPLO_CASO}
Resposta: {_EXEMPLO_JSON}
"""


def _montar_conteudo(texto_caso: str | None, intencao: str | None) -> str:
    """Combina o texto extraído do PDF com a intenção argumentativa digitada.

    RF03/§3.1 passo 5: quando os dois existem, ambos alimentam o enriquecimento —
    o texto do caso dá o contexto factual, a intenção diz o que o advogado quer
    sustentar.

    Input:  texto_caso — texto extraído do PDF, ou None/"" se não houve upload;
            intencao — intenção argumentativa digitada, ou None/"".
    Returns: conteúdo único a enviar ao LLM.
    Raises: ValueError se as duas fontes estiverem vazias (nada para enriquecer).
    """
    partes = []
    if texto_caso and texto_caso.strip():
        partes.append(f"Texto do processo:\n{texto_caso.strip()}")
    if intencao and intencao.strip():
        partes.append(f"Intenção argumentativa do advogado:\n{intencao.strip()}")
    if not partes:
        raise ValueError(
            "Nada para enriquecer: nem texto de PDF nem intenção argumentativa foram informados."
        )
    return "\n\n".join(partes)


class QueryEnricher:
    """Cliente de enriquecimento de query sobre o Ollama (Llama 3.2 3B)."""

    def __init__(self, model: str = DEFAULT_MODEL, client: ollama.Client | None = None) -> None:
        """Monta o cliente Ollama.

        Input:  model — nome do modelo; client — cliente Ollama (injeta em teste).
        Returns: None.
        """
        self.model = model
        self._client = client or ollama.Client(host=OLLAMA_HOST)

    def extract_estrutura(self, texto_caso: str | None, intencao: str | None = None) -> EstruturaArgumentativa:
        """Extrai a EstruturaArgumentativa via LLM (RF02).

        Input:  texto_caso — texto do PDF (já resumido, se longo); intencao —
                intenção argumentativa digitada.
        Returns: EstruturaArgumentativa validada.
        Raises: ValueError se não houver texto/intenção (propagado de _montar_conteudo).
        """
        conteudo = _montar_conteudo(texto_caso, intencao)
        resp = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": conteudo},
            ],
            format=EstruturaArgumentativa.model_json_schema(),
            options={"temperature": 0},
        )
        return EstruturaArgumentativa.model_validate_json(resp.message.content)

    def resumir_bloco(self, texto: str) -> str:
        """Resume um bloco de texto do PDF (usado na sumarização hierárquica — FA04).

        Input:  texto — um bloco do documento.
        Returns: resumo em 2-3 frases, preservando fatos e normas citadas.
        """
        resp = self._client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Resuma o trecho de processo trabalhista a seguir em até 3 "
                        "frases, preservando fatos, agentes de risco e normas citadas. "
                        "Não invente informação."
                    ),
                },
                {"role": "user", "content": texto},
            ],
            options={"temperature": 0},
        )
        return resp.message.content.strip()

    def condensar(self, resumos: list[str]) -> str:
        """Condensa vários resumos de blocos numa tese única (FA04).

        Input:  resumos — resumos individuais dos blocos do documento.
        Returns: texto único condensando os resumos, pronto para o Query Enrichment.
        """
        resp = self._client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "A seguir estão resumos de blocos sucessivos de um mesmo "
                        "processo trabalhista. Condense-os num único texto coeso, "
                        "preservando todos os fatos, agentes de risco e normas citadas. "
                        "Não invente informação."
                    ),
                },
                {"role": "user", "content": "\n\n".join(resumos)},
            ],
            options={"temperature": 0},
        )
        return resp.message.content.strip()
