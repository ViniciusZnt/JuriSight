"""
Filtro restrito no Postgres: autocompletar de dispositivos, contagens e ids elegíveis.
Depende de `python -m query.filtros.preparar` (tabelas de dispositivos e índice de texto).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import psycopg

from query.filtros.dispositivos import rotulo, tokens_da_busca
from query.filtros.expressoes import tsquery_da_expressao
from query.filtros.fases import Fase, condicao_fase

_CONTAGEM = "SELECT count(*) FROM public.documento_tsv d WHERE "


class FiltroIndisponivel(Exception):
    """O preparo (`python -m query.filtros.preparar`) ainda não rodou."""


@dataclass
class SugestaoDispositivo:
    codigo: str
    rotulo: str
    total: int


@dataclass
class ContagemFiltros:
    total: int
    dispositivos: list[SugestaoDispositivo]
    expressoes: list[tuple[str, int]]


def _filtros(dispositivos: list[str], tsqueries: list[str],
             tribunais: list[str] = (), fase: Fase | None = None) -> tuple[str, list]:
    """Cláusulas WHERE (todas as condições) e parâmetros; '' se não há filtro."""
    cond = ["EXISTS (SELECT 1 FROM public.documento_dispositivo x WHERE x.documento_id = d.id AND x.codigo = %s)"
            for _ in dispositivos]
    cond += [f"d.tsv @@ to_tsquery('simple', %s)" for _ in tsqueries]
    params: list = [*dispositivos, *tsqueries]
    if tribunais:
        cond.append("EXISTS (SELECT 1 FROM public.documentos x WHERE x.id = d.id AND x.tribunal = ANY(%s))")
        params.append(list(tribunais))
    if fase:
        sql, p = condicao_fase(fase)
        cond.append(f"EXISTS (SELECT 1 FROM public.documentos x WHERE x.id = d.id AND {sql})")
        params += p
    return " AND ".join(cond), params


class FiltroStore:
    def __init__(self, database_url: str):
        self._url = database_url

    def _consultar(self, sql: str, params: list) -> list[tuple]:
        try:
            with psycopg.connect(self._url) as conn:
                return conn.execute(sql, params).fetchall()
        except psycopg.errors.UndefinedTable as e:
            raise FiltroIndisponivel("rode `python -m query.filtros.preparar`") from e

    def sugerir(self, texto: str, limite: int = 10) -> list[SugestaoDispositivo]:
        """Dispositivos cujo código tem todos os tokens (qualquer ordem); o último vale como prefixo."""
        t = tokens_da_busca(texto)
        if not t:
            return []
        sql = "SELECT codigo, total FROM public.dispositivo WHERE true"
        params: list = []
        if t[:-1]:
            sql += " AND string_to_array(codigo, '_') @> %s::text[]"
            params.append(t[:-1])
        sql += (" AND EXISTS (SELECT 1 FROM unnest(string_to_array(codigo, '_')) x WHERE x LIKE %s || '%%')"
                " ORDER BY total DESC, codigo LIMIT %s")
        params += [t[-1], limite]
        return [SugestaoDispositivo(c, rotulo(c), n) for c, n in self._consultar(sql, params)]

    def elegiveis(self, dispositivos: list[str], expressoes: list[str],
                  tribunais: list[str] = (), fase: Fase | None = None) -> list[str]:
        """Ids das decisões que cumprem TODOS os dispositivos e expressões, em algum dos tribunais e na fase."""
        where, params = _filtros(dispositivos, [q for q in map(tsquery_da_expressao, expressoes) if q], tribunais, fase)
        if not where:
            return []
        return [str(i) for (i,) in self._consultar(f"SELECT d.id FROM public.documento_tsv d WHERE {where}", params)]

    def contar(self, dispositivos: list[str], expressoes: list[str],
               tribunais: list[str] = (), fase: Fase | None = None) -> ContagemFiltros:
        """Total elegível, mais quantas decisões têm cada dispositivo e cada expressão sozinhos.
        As consultas rodam em paralelo, cada uma na sua conexão: a de cada expressão relê o tsvector
        de milhares de decisões (~0,3 a 0,5 s), e em sequência três expressões comuns passavam de 1 s.
        Uma varredura só com `count(*) FILTER` foi medida e é mais lenta (relê o tsvector por filtro)."""
        pares = [(e, tsquery_da_expressao(e)) for e in expressoes]
        validas = list(dict.fromkeys(q for _, q in pares if q))
        where, params = _filtros(dispositivos, validas, tribunais, fase)
        uma_expressao = not dispositivos and len(validas) == 1 and not tribunais and not fase  # o total é a própria contagem dela
        consultas = [("SELECT codigo, total FROM public.dispositivo WHERE codigo = ANY(%s)", [dispositivos])]
        consultas += [(_CONTAGEM + "d.tsv @@ to_tsquery('simple', %s)", [q]) for q in validas]
        if where and not uma_expressao:
            consultas.append((_CONTAGEM + where, params))
        with ThreadPoolExecutor(max_workers=4) as pool:
            codigos, *contagens = pool.map(lambda c: self._consultar(*c), consultas)
        por_tsquery = {q: n[0][0] for q, n in zip(validas, contagens)}
        total = contagens[-1][0][0] if where else 0  # a última é o total (ou a expressão, se é o único filtro)
        por_codigo = dict(codigos)
        disp = [SugestaoDispositivo(c, rotulo(c), por_codigo.get(c, 0)) for c in dispositivos]
        return ContagemFiltros(total, disp, [(e, por_tsquery.get(q, 0)) for e, q in pares])

    def tribunais(self) -> list[tuple[str, int]]:
        """Tribunais do acervo com o total de decisões: TRT1, TRT2… TRT24 e depois os demais."""
        sql = ("SELECT tribunal, count(*) FROM public.documentos WHERE tribunal IS NOT NULL GROUP BY tribunal "
               "ORDER BY substring(tribunal from '^TRT(\\d+)$')::int NULLS LAST, tribunal")
        return [(t, n) for t, n in self._consultar(sql, [])]

    def existentes(self, codigos: list[str]) -> set[str]:
        """Quais dos códigos existem em `public.dispositivo`."""
        return {c for (c,) in self._consultar(
            "SELECT codigo FROM public.dispositivo WHERE codigo = ANY(%s)", [codigos])}
