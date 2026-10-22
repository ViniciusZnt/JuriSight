"""Benchmark multissistema (S0-S6): roda os sistemas e gera o relatório estatístico.

    python -m avaliacao.benchmark rodar [--sistemas S0,...,S6] [--split dev|teste|todos]
    python -m avaliacao.benchmark relatorio RUNS.json

`rodar` grava `data/eval/runs/<AAAA-MM-DD_HHMMSS>_runs.json` (top-20 e latência de
cada sistema por tese, mais os 30 candidatos do híbrido e o top-10 de BM25 e de
denso, para o teto e os relevantes perdidos). `relatorio` lê esse arquivo, junta
os rótulos finais do banco e grava `<mesmo prefixo>_relatorio.json`.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from avaliacao.eval import SAIDA_PADRAO, _commit_git
from avaliacao.metricas import (
    LIMIAR_RELEVANTE,
    ac2_gwet,
    alfa_krippendorff_ordinal,
    judged_at_k,
    kappa_ponderado_quadratico,
    map_at_k,
    mrr_at_k,
    ndcg_at_k,
    ndcg_teto,
    precisao_at_k,
    recall_at_k,
)
from avaliacao.sistemas import SISTEMAS, candidatos_hibrido, construir_rerankers, rodar_sistema, top_bm25, top_denso
from avaliacao.store import Tese

METRICAS = ("ndcg_10", "mrr_10", "p_5", "p_10", "recall_10", "map_10", "recall_20", "judged_10")
# (tratamento, controle): diferença = tratamento - controle em nDCG@10.
CONTRASTES = (("S3", "S2"), ("S4", "S3"), ("S5", "S3"), ("S6", "S3"), ("S0", "S2"), ("S1", "S2"))
N_BOOTSTRAP = 10_000
SEED_BOOTSTRAP = 42
WILCOXON_ZERO_METHOD = "pratt"


# --- rodar ------------------------------------------------------------------


def _nomes_dos_modelos(sistemas: list[str]) -> dict[str, str]:
    from query.search.reranker import MODEL_NAME
    from query.search.reranker_onnx import BGE, GTE

    todos = {"S3": MODEL_NAME, "S4": GTE[0], "S5": BGE[0], "S6": "unicamp-dl/monoptt5-base"}
    return {s: todos[s] for s in sistemas if s in todos}


def rodar(
    teses: list[Tese],
    deps,
    sistemas: list[str],
    rerankers: dict[str, object] | None = None,
    saida: Path | None = SAIDA_PADRAO,
) -> dict:
    """Roda cada sistema em todas as teses, um sistema por vez, medindo a latência.

    Input:  teses; deps (hybrid, retriever); sistemas ("S0".."S6");
            rerankers — dict pronto (testes) ou None: então o reranker de cada
            sistema é construído antes e liberado depois (`del` + gc), porque
            os modelos não cabem juntos na RAM; saida — diretório do JSON
            (None não grava).
    Returns: {"data", "commit", "sistemas", "modelos", "teses": [{tese_id, origem,
             tema, split, candidatos, top10_bm25, top10_denso,
             "sistemas": {S: {"ids": top-20, "latencia_s": float}}}], "arquivo"}.
    """
    desconhecidos = [s for s in sistemas if s not in SISTEMAS]
    if desconhecidos:
        raise ValueError(f"Sistema desconhecido: {desconhecidos} (esperado um de {SISTEMAS})")
    from query.enrichment.schema import EstruturaArgumentativa

    agora = datetime.now()
    linhas = []
    for tese in teses:
        # Pool de referência calculado uma vez por tese (teto e perdidos).
        est = EstruturaArgumentativa(**tese.estrutura)
        linhas.append({
            "tese_id": str(tese.id), "origem": tese.origem, "tema": tese.tema, "split": tese.split,
            "candidatos": candidatos_hibrido(est, hybrid=deps.hybrid, retriever=deps.retriever),
            "top10_bm25": top_bm25(deps.hybrid, est, 10),
            "top10_denso": top_denso(deps.hybrid, est, 10),
            "sistemas": {},
        })
    for sistema in sistemas:
        usados: dict[str, object] = {}
        if sistema in ("S0", "S1", "S2"):
            pass
        elif rerankers is not None:
            usados = rerankers
        else:
            usados = construir_rerankers([sistema])
        if teses:  # aquecimento sem cronometrar (cache de modelo, conexões, primeira chamada)
            rodar_sistema(sistema, EstruturaArgumentativa(**teses[0].estrutura), deps, usados)
        for tese, linha in zip(teses, linhas):
            est = EstruturaArgumentativa(**tese.estrutura)
            t0 = time.perf_counter()
            ids = rodar_sistema(sistema, est, deps, usados)
            linha["sistemas"][sistema] = {"ids": ids, "latencia_s": time.perf_counter() - t0}
        if rerankers is None:
            del usados
            gc.collect()
        print(f"{sistema} concluído ({len(teses)} teses)", file=sys.stderr)
    runs = {
        "data": agora.isoformat(timespec="seconds"),
        "commit": _commit_git(),
        "sistemas": list(sistemas),
        "modelos": _nomes_dos_modelos(sistemas),
        "teses": linhas,
        "arquivo": None,
    }
    if saida is not None:
        saida.mkdir(parents=True, exist_ok=True)
        caminho = saida / f"{agora:%Y-%m-%d_%H%M%S}_runs.json"
        runs["arquivo"] = str(caminho)
        caminho.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    return runs


# --- estatística ------------------------------------------------------------


def _holm(ps: list[float]) -> list[float]:
    """Ajuste de Holm (step-down) dos p-valores, na ordem original."""
    m = len(ps)
    ordem = sorted(range(m), key=lambda i: ps[i])
    ajustados = [0.0] * m
    maximo = 0.0
    for posicao, i in enumerate(ordem):
        maximo = max(maximo, min(1.0, (m - posicao) * ps[i]))
        ajustados[i] = maximo
    return ajustados


def _benjamini_hochberg(ps: list[float]) -> list[float]:
    """Ajuste de Benjamini-Hochberg (FDR) dos p-valores, na ordem original."""
    m = len(ps)
    ordem = sorted(range(m), key=lambda i: ps[i], reverse=True)
    ajustados = [0.0] * m
    minimo = 1.0
    for k, i in enumerate(ordem):
        rank = m - k
        minimo = min(minimo, ps[i] * m / rank)
        ajustados[i] = minimo
    return ajustados


def _p_valido(p) -> float | None:
    p = float(p)
    return None if np.isnan(p) else p


def _contraste(a: list[float], b: list[float]) -> dict:
    """Estatísticas brutas de a - b pareado (p ainda sem ajuste)."""
    from scipy import stats

    n = len(a)
    dif = np.array(a, dtype=float) - np.array(b, dtype=float)
    saida = {"n_teses": n, "diferenca_media": float(dif.mean()) if n else None,
             "ic95": None, "p_t": None, "p_wilcoxon": None}
    if n < 2:
        return saida
    rng = np.random.default_rng(SEED_BOOTSTRAP)
    medias = dif[rng.integers(0, n, size=(N_BOOTSTRAP, n))].mean(axis=1)
    saida["ic95"] = [float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))]
    if np.all(dif == 0):  # Wilcoxon levanta erro com todas as diferenças zero
        return saida
    if np.ptp(dif) > 1e-12:  # diferença constante (com folga de ponto flutuante): t indefinido
        saida["p_t"] = _p_valido(stats.ttest_rel(a, b).pvalue)
    try:
        saida["p_wilcoxon"] = _p_valido(stats.wilcoxon(a, b, zero_method=WILCOXON_ZERO_METHOD).pvalue)
    except ValueError:
        pass
    return saida


def _ajustar(contrastes: list[dict], chave: str, destino: str, ajuste: Callable) -> None:
    """Ajusta o p `chave` de todos os contrastes rodados e grava em `destino`.
    Contraste rodado sem p (degenerado) entra com p = 1,0; o p bruto fica None.
    Assim o m é sempre o número de contrastes rodados."""
    ps = [1.0 if c[chave] is None else c[chave] for c in contrastes]
    for c, p in zip(contrastes, ajuste(ps)):
        c[destino] = p


def calcular_contrastes(ndcg: dict[str, dict[str, float | None]]) -> tuple[list[dict], list[str], list[dict]]:
    """Contrastes registrados sobre o nDCG@10 por tese.

    Input:  ndcg — sistema -> (tese_id -> nDCG@10 ou None).
    Returns: (contrastes, avisos, omitidos). Entram só as teses em que os dois
    sistemas têm valor. Contraste de sistema ausente é omitido (com aviso) e
    fica fora da família do Holm/BH; os rodados contam todos no m.
    """
    contrastes, avisos, omitidos = [], [], []
    for trat, ctrl in CONTRASTES:
        if trat not in ndcg or ctrl not in ndcg:
            ausentes = [s for s in (trat, ctrl) if s not in ndcg]
            omitidos.append({"tratamento": trat, "controle": ctrl, "ausentes": ausentes})
            avisos.append(f"contraste {trat} x {ctrl} omitido: sistema(s) ausente(s) nas runs: {', '.join(ausentes)}")
            continue
        ids = [t for t in ndcg[trat] if ndcg[trat][t] is not None and ndcg[ctrl].get(t) is not None]
        c = _contraste([ndcg[trat][t] for t in ids], [ndcg[ctrl][t] for t in ids])
        contrastes.append({"tratamento": trat, "controle": ctrl, **c})
    _ajustar(contrastes, "p_t", "p_t_holm", _holm)
    _ajustar(contrastes, "p_wilcoxon", "p_wilcoxon_bh", _benjamini_hochberg)
    return contrastes, avisos, omitidos


# --- concordância -----------------------------------------------------------


def pares_de_avaliadores(julgamentos: list, adjudicador: str | None = None) -> list[tuple[int, int]]:
    """Notas brutas (antes do consenso) de dois avaliadores por par.

    Considera só juízes humanos, sem o adjudicador (`humano:<email>` normalizado).
    Por par com 2+ avaliadores, usa o julgamento mais recente de cada um (a lista
    vem em ordem de criação); com mais de dois, os dois primeiros juízes em ordem
    alfabética.
    """
    excluido = f"humano:{adjudicador.strip().lower()}" if adjudicador else None
    por_par: dict = {}
    for j in julgamentos:
        if j.juiz.startswith("humano:") and j.juiz != excluido:
            por_par.setdefault(j.par_id, {})[j.juiz] = j.relevancia  # o último vence
    return [
        (notas[juizes[0]], notas[juizes[1]])
        for notas in por_par.values()
        if len(juizes := sorted(notas)) >= 2
    ]


def concordancia(julgamentos: list, adjudicador: str | None = None) -> dict:
    pares = pares_de_avaliadores(julgamentos, adjudicador)
    return {
        "n_pares": len(pares),
        "kappa_ponderado": kappa_ponderado_quadratico([a for a, _ in pares], [b for _, b in pares]) if pares else None,
        "alfa_krippendorff": alfa_krippendorff_ordinal(pares) if pares else None,
        "ac2_gwet": ac2_gwet(pares) if pares else None,
    }


# --- avaliar ----------------------------------------------------------------


def _metricas_da_tese(ids: list[str], ganhos: dict[str, int]) -> dict[str, float | None]:
    return {
        "ndcg_10": ndcg_at_k(ids, ganhos, 10),
        "mrr_10": mrr_at_k(ids, ganhos, 10),
        "p_5": precisao_at_k(ids, ganhos, 5),
        "p_10": precisao_at_k(ids, ganhos, 10),
        "recall_10": recall_at_k(ids, ganhos, 10),
        "map_10": map_at_k(ids, ganhos, 10),
        "recall_20": recall_at_k(ids, ganhos, 20),
        "judged_10": judged_at_k(ids, ganhos, 10) if ganhos else None,
    }


def _media(valores: list[float | None]) -> tuple[float | None, int]:
    presentes = [v for v in valores if v is not None]
    return (float(np.mean(presentes)) if presentes else None), len(valores) - len(presentes)


def avaliar_runs(
    runs: dict,
    rotulos: Callable[[uuid.UUID], tuple[dict[str, int], dict[str, str]]],
    julgamentos: list | None = None,
    pendentes: list | None = None,
    adjudicador: str | None = None,
) -> dict:
    """Métricas por tese e sistema, médias com excluídas, latência, teto, perdidos,
    contrastes e concordância.

    Input:  runs (saída de `rodar`); rotulos(tese_id) -> (ganhos, stances);
            julgamentos (todos, para a concordância); pendentes (store.pendentes).
    """
    sistemas = [s for s in SISTEMAS if s in runs["sistemas"]]
    por_tese, tetos, perdidos = [], [], []
    for linha in runs["teses"]:
        ganhos, _ = rotulos(uuid.UUID(linha["tese_id"]))
        por_tese.append({
            "tese_id": linha["tese_id"], "origem": linha["origem"], "tema": linha["tema"],
            "split": linha["split"], "n_rotulados": len(ganhos),
            "sistemas": {
                s: {**_metricas_da_tese(linha["sistemas"][s]["ids"], ganhos),
                    "latencia_s": linha["sistemas"][s]["latencia_s"]}
                for s in sistemas if s in linha["sistemas"]
            },
        })
        tetos.append(ndcg_teto(linha["candidatos"], ganhos, 10))
        fora = set(linha["candidatos"])
        achados = sorted(
            d for d in set(linha["top10_bm25"]) | set(linha["top10_denso"])
            if d not in fora and ganhos.get(d, 0) >= LIMIAR_RELEVANTE
        )
        perdidos.append({"tese_id": linha["tese_id"], "n": len(achados), "documentos": achados})

    por_sistema = {}
    for s in sistemas:
        linhas = [t["sistemas"][s] for t in por_tese if s in t["sistemas"]]
        medias, excluidas = {}, {}
        for m in METRICAS:
            medias[m], excluidas[m] = _media([l[m] for l in linhas])
        lat = [l["latencia_s"] for l in linhas]
        por_sistema[s] = {
            "n_teses": len(linhas), "medias": medias, "excluidas": excluidas,
            "latencia_mediana_s": float(np.median(lat)) if lat else None,
            "latencia_p95_s": float(np.percentile(lat, 95)) if lat else None,
        }

    ndcg = {s: {t["tese_id"]: t["sistemas"][s]["ndcg_10"] for t in por_tese if s in t["sistemas"]} for s in sistemas}
    contrastes, avisos, omitidos = calcular_contrastes(ndcg)
    teto_medio, teto_excluidas = _media(tetos)
    return {
        "data": runs.get("data"), "commit": runs.get("commit"), "modelos": runs.get("modelos", {}),
        "sistemas": sistemas, "n_teses": len(por_tese),
        "por_tese": por_tese, "por_sistema": por_sistema,
        "contrastes": contrastes, "avisos": avisos,
        "estatistica": {
            "m_holm": len(contrastes), "m_bh": len(contrastes),
            "contrastes_omitidos": omitidos,
            "wilcoxon_zero_method": WILCOXON_ZERO_METHOD,
            "bootstrap": {"reamostragens": N_BOOTSTRAP, "seed": SEED_BOOTSTRAP},
        },
        "teto": {"ndcg_10_medio": teto_medio, "excluidas": teto_excluidas, "por_tese": tetos},
        "perdidos": {"total": sum(p["n"] for p in perdidos), "por_tese": perdidos},
        "concordancia": concordancia(julgamentos or [], adjudicador),
        "pendentes": len(pendentes or []),
    }


# --- impressão e CLI --------------------------------------------------------


def _f(v: float | None, casas: int = 3) -> str:
    return "-" if v is None else f"{v:.{casas}f}"


def imprimir_relatorio(rel: dict) -> None:
    print(f"commit={rel['commit']} teses={rel['n_teses']} modelos={rel['modelos']}")
    cab = ("sist", "nDCG@10", "MRR@10", "P@5", "P@10", "Rec@10", "MAP@10", "Judg@10", "lat med s", "lat p95 s")
    print("".join(f"{c:>11}" for c in cab))
    for s, g in rel["por_sistema"].items():
        m = g["medias"]
        cel = [m[k] for k in ("ndcg_10", "mrr_10", "p_5", "p_10", "recall_10", "map_10", "judged_10")]
        print(f"{s:>11}" + "".join(f"{_f(v):>11}" for v in cel)
              + f"{_f(g['latencia_mediana_s'], 2):>11}{_f(g['latencia_p95_s'], 2):>11}")
        exc = {k: v for k, v in g["excluidas"].items() if v}
        if exc:
            print(f"{'':>11}teses excluídas por métrica: {exc}")
    if all(g["medias"]["ndcg_10"] is None for g in rel["por_sistema"].values()):
        print("(sem rótulos: métricas de ranking indisponíveis)")
    print("\nContrastes em nDCG@10 (tratamento - controle)")
    for c in rel["contrastes"]:
        ic = "-" if c["ic95"] is None else f"[{c['ic95'][0]:+.3f}, {c['ic95'][1]:+.3f}]"
        print(f"  {c['tratamento']} x {c['controle']}: n={c['n_teses']} dif={_f(c['diferenca_media'])} IC95={ic} "
              f"t(Holm)={_f(c['p_t_holm'], 4)} Wilcoxon(BH)={_f(c['p_wilcoxon_bh'], 4)}")
    est = rel["estatistica"]
    print(f"  m(Holm)={est['m_holm']} m(BH)={est['m_bh']} Wilcoxon zero_method={est['wilcoxon_zero_method']}")
    for aviso in rel["avisos"]:
        print(f"  aviso: {aviso}")
    print(f"\nTeto (nDCG@10 ideal dos 30 candidatos): {_f(rel['teto']['ndcg_10_medio'])} "
          f"(excluídas: {rel['teto']['excluidas']})")
    print(f"Relevantes (>=2) perdidos pelo híbrido (top-10 de BM25/denso fora dos 30): {rel['perdidos']['total']}")
    c = rel["concordancia"]
    print(f"Concordância ({c['n_pares']} pares): kappa={_f(c['kappa_ponderado'])} "
          f"alfa={_f(c['alfa_krippendorff'])} AC2={_f(c['ac2_gwet'])}")
    print(f"Pares pendentes: {rel['pendentes']}")


def _cmd_rodar(args) -> int:
    from avaliacao.contexto import carregar_dependencias

    sistemas = [s.strip().upper() for s in args.sistemas.split(",") if s.strip()]
    deps = carregar_dependencias()  # lento: BM25, embedder e FlashRank
    deps.reranker = None  # os rerankers são construídos um por vez em `rodar`
    teses = deps.store.listar_teses(None if args.split == "todos" else args.split)
    if not teses:
        print(f"Aviso: nenhuma tese no split '{args.split}'.", file=sys.stderr)
        return 1
    runs = rodar(teses, deps, sistemas, None, args.saida)
    for s in runs["sistemas"]:
        lat = [t["sistemas"][s]["latencia_s"] for t in runs["teses"]]
        print(f"{s}: mediana={np.median(lat):.2f}s p95={np.percentile(lat, 95):.2f}s")
    print(f"Runs gravadas em {runs['arquivo']}")
    return 0


def _cmd_relatorio(args) -> int:
    from avaliacao.contexto import carregar_store

    runs = json.loads(args.runs.read_text(encoding="utf-8"))
    adjudicador = (os.getenv("AVALIACAO_ADJUDICADOR") or "").strip().lower() or None
    store = carregar_store()
    rel = avaliar_runs(
        runs, lambda tid: store.rotulos_finais(tid, adjudicador),
        julgamentos=store.julgamentos("humano:"), pendentes=store.pendentes(adjudicador),
        adjudicador=adjudicador,
    )
    destino = args.runs.with_name(args.runs.name.removesuffix("_runs.json").removesuffix(".json") + "_relatorio.json")
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    imprimir_relatorio(rel)
    print(f"Relatório gravado em {destino}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao.benchmark", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p_rodar = sub.add_parser("rodar", help="roda os sistemas e grava as runs")
    p_rodar.add_argument("--sistemas", default=",".join(SISTEMAS))
    p_rodar.add_argument("--split", default="todos", choices=("dev", "teste", "todos"))
    p_rodar.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    p_rodar.set_defaults(func=_cmd_rodar)
    p_rel = sub.add_parser("relatorio", help="calcula métricas e contrastes de um arquivo de runs")
    p_rel.add_argument("runs", type=Path)
    p_rel.set_defaults(func=_cmd_relatorio)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
