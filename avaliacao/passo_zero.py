"""
Passo 0 do harness: testa o juiz Jev em português antes de construir o conjunto
de avaliação. A Alexia rotula à mão uma amostra pequena (sem ver a nota do Jev)
e comparamos os rótulos dela com os do Jev nas rodadas 1 e 2.

    python -m avaliacao.passo_zero preparar [--teses 5] [--por-tese 4] [--sim]
    python -m avaliacao.passo_zero comparar [--csv ...] [--rotulador email]
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import uuid
from pathlib import Path

from avaliacao.metricas import kappa_cohen, kappa_ponderado_quadratico
from avaliacao.store import Julgamento

CSV_PADRAO = Path(__file__).resolve().parent.parent / "data" / "eval" / "passo_zero.csv"
COLUNAS_CSV = ["par_id", "tese", "ementa", "link", "relevancia_alexia", "stance_alexia"]
STANCES = ("fortalece", "enfraquece", "neutro")
CORREDOR = "passo_zero"
TOKENS_POR_JULGAMENTO = 1300
RODADAS = (1, 2)
RODADA_HUMANO = 1  # convenção: humanos gravam na rodada 1


def _aviso(msg: str) -> None:
    print(msg, file=sys.stderr)


# --- escolha dos documentos -------------------------------------------------


def escolher_docs(teses: list[dict], por_tese: int, seed: int) -> list[list[str]]:
    """Escolhe, por tese, os documentos a julgar (sem repetir na mesma tese).

    `teses`: lista de {"tema": str, "ranking": [documento_id, ...]} (ranking do
    `buscar`, melhor primeiro). Devolve uma lista de ids por tese, na mesma ordem,
    com até `por_tese` itens, preenchidos nesta ordem:
      1-2. os dois primeiros do ranking;
      3.   um sorteado das posições 15-20 do ranking (índices 14..19);
      4.   um dos dois primeiros de OUTRA tese do lote, de preferência de tema
           diferente (senão de qualquer outra); sem outra tese, o slot é pulado.
    Slot sem candidato (ranking curto, tudo repetido) também é pulado.
    """
    resultado: list[list[str]] = []
    for i, tese in enumerate(teses):
        rng = random.Random(f"{seed}:{i}")
        ranking = tese["ranking"]
        escolhidos: list[str] = list(ranking[: min(2, por_tese)])

        if len(escolhidos) < por_tese:
            cauda = [d for d in ranking[14:20] if d not in escolhidos]
            if cauda:
                escolhidos.append(rng.choice(cauda))

        if len(escolhidos) < por_tese:
            outras = [t for j, t in enumerate(teses) if j != i]
            diferentes = [t for t in outras if t["tema"] != tese["tema"]]
            candidatos = [
                d
                for t in (diferentes or outras)
                for d in t["ranking"][:2]
                if d not in escolhidos
            ]
            if candidatos:
                escolhidos.append(rng.choice(candidatos))

        resultado.append(escolhidos)
    return resultado


# --- CSV --------------------------------------------------------------------


def escrever_csv(caminho: Path, linhas: list[dict]) -> None:
    """Escreve o CSV da Alexia: par_id, tese, ementa, link e as duas colunas em
    branco para ela preencher. Não inclui nada do Jev. utf-8 com BOM para o Excel
    abrir os acentos corretamente."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_CSV)
        w.writeheader()
        for linha in linhas:
            w.writerow(
                {
                    "par_id": str(linha["par_id"]),
                    "tese": linha["tese"],
                    "ementa": linha["ementa"],
                    "link": linha["link"],
                    "relevancia_alexia": "",
                    "stance_alexia": "",
                }
            )


def ler_csv(caminho: Path) -> list[tuple[uuid.UUID, int, str]]:
    """Lê (par_id, relevância, stance) das linhas preenchidas.

    Linhas sem relevância ou sem stance são ignoradas em silêncio (ainda não
    rotuladas). Linhas preenchidas porém inválidas (par_id que não é UUID,
    relevância fora de 0-3, stance fora de fortalece/enfraquece/neutro) geram
    aviso em stderr e são puladas.
    """
    lidos: list[tuple[uuid.UUID, int, str]] = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for numero, linha in enumerate(csv.DictReader(f), start=2):
            rel_txt = (linha.get("relevancia_alexia") or "").strip()
            stance_txt = (linha.get("stance_alexia") or "").strip().lower()
            if not rel_txt or not stance_txt:
                continue
            par_txt = (linha.get("par_id") or "").strip()
            try:
                par_id = uuid.UUID(par_txt)
            except ValueError:
                _aviso(f"linha {numero}: par_id inválido ({par_txt!r}); pulada")
                continue
            if rel_txt not in ("0", "1", "2", "3"):
                _aviso(f"linha {numero} (par {par_id}): relevância {rel_txt!r} fora de 0-3; pulada")
                continue
            if stance_txt not in STANCES:
                _aviso(
                    f"linha {numero} (par {par_id}): stance {stance_txt!r} fora de "
                    f"{'/'.join(STANCES)}; pulada"
                )
                continue
            lidos.append((par_id, int(rel_txt), stance_txt))
    return lidos


def ler_ids_csv(caminho: Path) -> list[uuid.UUID]:
    """Todos os par_ids válidos do CSV, rotulados ou não."""
    ids: list[uuid.UUID] = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            try:
                ids.append(uuid.UUID((linha.get("par_id") or "").strip()))
            except ValueError:
                continue
    return ids


def csv_tem_rotulos(caminho: Path) -> bool:
    """True se o arquivo existe e alguma linha tem relevância ou stance preenchida."""
    if not Path(caminho).exists():
        return False
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return any(
            (l.get("relevancia_alexia") or "").strip() or (l.get("stance_alexia") or "").strip()
            for l in csv.DictReader(f)
        )


# --- comparação -------------------------------------------------------------


def jev_das_rodadas(
    julgamentos: list[Julgamento], par_ids: set[uuid.UUID]
) -> tuple[list[Julgamento], list[Julgamento]]:
    """Separa os julgamentos do Jev em (rodada 1, rodada 2), só dos pares dados.

    Sem o filtro, pares de outras execuções (ex.: a amostra do eval) entrariam
    na concordância entre rodadas."""
    dos_pares = [j for j in julgamentos if j.par_id in par_ids]
    return (
        [j for j in dos_pares if j.rodada == 1],
        [j for j in dos_pares if j.rodada == 2],
    )


def resumo_comparacao(
    humanos: list[Julgamento], jev1: list[Julgamento], jev2: list[Julgamento]
) -> dict:
    """Compara os rótulos humanos com o Jev rodada 1 e as duas rodadas do Jev.

    Os pares são casados por `par_id`; cada métrica usa só os pares presentes
    nas duas listas que ela compara. Chaves do resultado:
      n                    pares presentes em `humanos` e `jev1`
      kappa_relevancia     kappa ponderado quadrático humano x jev1 (ou None)
      kappa_stance         kappa de Cohen humano x jev1 (ou None)
      n_rodadas            pares presentes em `jev1` e `jev2`
      concordancia_rodadas fração desses pares com a mesma relevância E a mesma
                           stance nas duas rodadas (ou None se n_rodadas == 0)
      matriz_stance        {stance_humana: {stance_jev1: contagem}}
    """
    h = {j.par_id: j for j in humanos}
    j1 = {j.par_id: j for j in jev1}
    j2 = {j.par_id: j for j in jev2}

    comuns = [p for p in h if p in j1]
    kappa_rel = kappa_ponderado_quadratico(
        [h[p].relevancia for p in comuns], [j1[p].relevancia for p in comuns]
    )
    kappa_stance = kappa_cohen([h[p].stance for p in comuns], [j1[p].stance for p in comuns])
    matriz: dict[str, dict[str, int]] = {}
    for p in comuns:
        linha = matriz.setdefault(h[p].stance, {})
        linha[j1[p].stance] = linha.get(j1[p].stance, 0) + 1

    entre_rodadas = [p for p in j1 if p in j2]
    iguais = sum(
        1
        for p in entre_rodadas
        if j1[p].relevancia == j2[p].relevancia and j1[p].stance == j2[p].stance
    )
    return {
        "n": len(comuns),
        "kappa_relevancia": kappa_rel,
        "kappa_stance": kappa_stance,
        "n_rodadas": len(entre_rodadas),
        "concordancia_rodadas": iguais / len(entre_rodadas) if entre_rodadas else None,
        "matriz_stance": matriz,
    }


def confirmar(pergunta: str) -> bool:
    """Pergunta s/N; sem terminal interativo (EOF) conta como não."""
    try:
        return input(pergunta).strip().lower() == "s"
    except EOFError:
        return False


def _carregar_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(CSV_PADRAO.parent.parent.parent / ".env")


def _fmt(valor: float | None) -> str:
    return "indefinido" if valor is None else f"{valor:.3f}"


def _imprimir_resumo(r: dict) -> None:
    print(f"Pares comparados (humano x Jev rodada 1): {r['n']}")
    print(f"Kappa ponderado (relevância): {_fmt(r['kappa_relevancia'])}")
    print(f"Kappa (stance):               {_fmt(r['kappa_stance'])}")
    print(
        f"Concordância rodada 1 x 2:    {_fmt(r['concordancia_rodadas'])} "
        f"({r['n_rodadas']} pares)"
    )
    print("Matriz de stance (linhas = humano, colunas = Jev rodada 1):")
    print("  " + " " * 11 + "".join(f"{s:>12}" for s in STANCES))
    for humano in STANCES:
        linha = r["matriz_stance"].get(humano, {})
        print("  " + f"{humano:<11}" + "".join(f"{linha.get(s, 0):>12}" for s in STANCES))


# --- comandos ---------------------------------------------------------------


def _uuids_origem(database_url: str, docs) -> dict[str, str]:
    """id_documento (chave natural do portal) -> UUID em `documentos`.

    `sortear_acordaos` devolve DocumentoJuridico sem o UUID, e os pares usam UUID."""
    import psycopg

    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            "SELECT id_documento, id::text FROM documentos WHERE id_documento = ANY(%s)",
            ([d.id_documento for d in docs],),
        ).fetchall()
    return dict(rows)


def preparar(n_teses: int, por_tese: int, sim: bool, caminho: Path) -> int:
    if csv_tem_rotulos(caminho):
        _aviso(
            f"{caminho} já tem rótulos preenchidos; recusando sobrescrever. "
            "Mova ou apague o arquivo se for mesmo recomeçar."
        )
        return 1
    tokens = n_teses * por_tese * len(RODADAS) * TOKENS_POR_JULGAMENTO
    print(
        f"Chamadas pagas: OpenAI ({n_teses} teses) e Jev ({n_teses} temas + "
        f"{n_teses * por_tese} pares x {len(RODADAS)} rodadas).\n"
        f"Estimativa Jev: {n_teses * por_tese} pares x {len(RODADAS)} x ~{TOKENS_POR_JULGAMENTO} "
        f"= ~{tokens} tokens"
    )
    if not sim and not confirmar("Continuar? [s/N] "):
        print("Cancelado.")
        return 1

    from typesafe_sdk import TypeSafeClient

    from avaliacao.contexto import carregar_dependencias
    from avaliacao.geracao import gerar_tese, sortear_acordaos, sortear_split
    from avaliacao.juiz import JuizJev, julgar_lote
    from avaliacao.temas import TEMAS, atribuir_tema
    from query.enrichment import query_builder
    from query.search.pipeline import buscar

    seed = int(os.getenv("AVALIACAO_SEED", "42"))
    deps = carregar_dependencias()
    client = TypeSafeClient()
    juiz = JuizJev(client=client)
    splits = sortear_split(TEMAS, seed)

    acordaos = sortear_acordaos(deps.database_url, n_teses, seed)
    uuids = _uuids_origem(deps.database_url, acordaos)
    n_favoravel = (n_teses + 1) // 2  # mesma regra de sortear_acordaos

    registros: list[dict] = []
    for i, acordao in enumerate(acordaos):
        lado = "favoravel" if i < n_favoravel else "contrario"
        if acordao.id_documento not in uuids:
            _aviso(f"Acórdão {acordao.id_documento}: UUID não encontrado em documentos; tese {i + 1} pulada")
            continue
        try:
            estrutura = gerar_tese(acordao, lado)
            dados = estrutura.model_dump()
            tema = atribuir_tema(dados, client=client)
            ranking = [c.id for c in buscar(
                estrutura, hybrid=deps.hybrid, retriever=deps.retriever, reranker=deps.reranker
            )]
        except Exception as e:  # noqa: BLE001 — uma tese ruim não deve derrubar o lote
            _aviso(f"Tese {i + 1} ({acordao.id_documento}) descartada: {e}")
            continue
        tese = deps.store.criar_tese(
            dados, "sintetica", tema, splits[tema],
            documento_origem_id=uuids[acordao.id_documento],
        )
        print(f"Tese {i + 1}/{len(acordaos)} ({lado}, tema: {tema}): {len(ranking)} resultados")
        registros.append({"tese": tese, "estrutura": estrutura, "dados": dados, "ranking": ranking})

    if not registros:
        _aviso("Nenhuma tese foi gerada.")
        return 1

    escolhidos = escolher_docs(
        [{"tema": r["tese"].tema, "ranking": r["ranking"]} for r in registros], por_tese, seed
    )
    documentos = deps.retriever.fetch(sorted({d for ids in escolhidos for d in ids}))

    linhas: list[dict] = []
    itens_por_par: list[tuple] = []
    for registro, ids in zip(registros, escolhidos):
        ids = [d for d in ids if d in documentos]
        pares = deps.store.adicionar_pares(registro["tese"].id, {d: [CORREDOR] for d in ids})
        frase = query_builder.build_frase_tese(registro["estrutura"])
        for par in pares:
            doc = documentos[par.documento_id]
            itens_por_par.append((par.id, registro["dados"], doc))
            linhas.append(
                {"par_id": par.id, "tese": frase, "ementa": doc.ementa, "link": doc.link_original or ""}
            )

    random.Random(seed).shuffle(linhas)  # a posição no CSV não deve revelar a origem do par
    escrever_csv(caminho, linhas)
    print(f"{len(linhas)} pares gravados em {caminho}")

    falhou = False
    for rodada in RODADAS:
        ok = julgar_lote(juiz, itens_por_par, rodada, deps.store.gravar_julgamento)
        print(f"Jev rodada {rodada}: {ok}/{len(itens_por_par)} julgamentos")
        if ok < len(itens_por_par):
            _aviso(f"Atenção: {len(itens_por_par) - ok} julgamento(s) da rodada {rodada} falharam.")
            falhou = True
    return 1 if falhou else 0


def comparar(caminho: Path, rotulador: str | None) -> int:
    if not Path(caminho).exists():
        _aviso(f"CSV não encontrado: {caminho}. Rode `preparar` primeiro ou passe --csv.")
        return 2
    _carregar_env()
    if not rotulador:
        emails = [e.strip() for e in os.getenv("AVALIACAO_EMAILS", "").split(",") if e.strip()]
        if not emails:
            _aviso("Informe --rotulador ou defina AVALIACAO_EMAILS no .env.")
            return 2
        rotulador = emails[0]

    from avaliacao.contexto import carregar_store

    store = carregar_store()

    jev = store.julgamentos("jev:")
    conhecidos = {j.par_id for j in jev}
    # A concordância entre rodadas usa todos os pares do CSV, rotulados ou não.
    jev1, jev2 = jev_das_rodadas(jev, set(ler_ids_csv(caminho)))

    humanos: list[Julgamento] = []
    for par_id, rel, stance in ler_csv(caminho):
        if par_id not in conhecidos:
            _aviso(f"par {par_id} não existe no banco (sem julgamento do Jev); pulado")
            continue
        humanos.append(
            Julgamento(par_id=par_id, juiz=f"humano:{rotulador}", rodada=RODADA_HUMANO,
                       relevancia=rel, stance=stance)
        )
    for h in humanos:
        store.gravar_julgamento(h)
    print(f"{len(humanos)} rótulo(s) de humano:{rotulador} gravados.\n")

    _imprimir_resumo(resumo_comparacao(humanos, jev1, jev2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao.passo_zero", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("preparar", help="gera teses, busca, julga com o Jev e escreve o CSV")
    p.add_argument("--teses", type=int, default=5)
    p.add_argument("--por-tese", type=int, default=4)
    p.add_argument("--csv", type=Path, default=CSV_PADRAO)
    p.add_argument("--sim", action="store_true", help="pula a confirmação de custo")

    c = sub.add_parser("comparar", help="grava os rótulos do CSV e compara com o Jev")
    c.add_argument("--csv", type=Path, default=CSV_PADRAO)
    c.add_argument("--rotulador", help="e-mail do rotulador (padrão: 1º de AVALIACAO_EMAILS)")

    args = parser.parse_args(argv)
    if args.comando == "preparar":
        return preparar(args.teses, args.por_tese, args.sim, args.csv)
    return comparar(args.csv, args.rotulador)


if __name__ == "__main__":
    sys.exit(main())
