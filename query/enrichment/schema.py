"""
Schema da EstruturaArgumentativa (RFC §5.2, Tabela 10).

Entidade de memória de sessão — extraída via LLM do PDF do caso e/ou da intenção
argumentativa digitada pelo usuário, revisada por ele antes da busca (RN05).
NUNCA é persistida no PostgreSQL (fonte de verdade é só para DocumentoJuridico —
os acórdãos já coletados do TST; ver §6.1 LGPD).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EstruturaArgumentativa(BaseModel):
    """Entendimento do caso do advogado, conforme a Tabela 10 da RFC.

    Todo campo tem default (string vazia, lista vazia ou None) — se o LLM não
    encontrar um valor no texto, o campo fica no default, nunca inventado (RN05).
    """

    pedido_principal: str = ""
    agente_nocivo: list[str] = Field(default_factory=list)
    violacoes: list[str] = Field(default_factory=list)
    normas: list[str] = Field(default_factory=list)
    dispositivos: list[str] = Field(default_factory=list)  # códigos (ex.: art_192_clt) — filtro restrito
    expressoes: list[str] = Field(default_factory=list)  # expressões obrigatórias — filtro restrito
    tribunais: list[str] = Field(default_factory=list)  # ex.: TRT4 (OU entre eles) — filtro restrito
    fase: Literal["conhecimento", "execucao", "outras"] | None = None  # filtro restrito
    empresa_ciente: bool | None = None
    setor: str | None = None
    cargo: str | None = None
    tese_central: str = ""
