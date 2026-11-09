"""
Comando `eval` do harness: roda a busca do JuriSight para cada tese do
conjunto-ouro, calcula as métricas de ranking contra os rótulos finais e grava
um relatório JSON por execução.

    python -m avaliacao.eval --split {dev,teste} [--saida data/eval/runs/]

Roda a busca real (Qdrant, índice BM25 e embedding da OpenAI).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from avaliacao.metricas import fracao_fortalece, fracao_nao_julgados, ndcg_at_k, recall_at_k
from avaliacao.store import Tese

SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "eval" / "runs"
METRICAS = ("ndcg_10", "recall_20", "fortalece_10", "nao_julgados_10")


# --- métricas de ranking ----------------------------------------------------


def _media(valores: list[float | None]) -> tuple[float | None, int]:
    """(média ignorando None, quantos None)."""
    presentes = [v for v in valores if v is not None]
    excluidas = len(valores) - len(presentes)
    return (sum(presentes) / len(presentes) if presentes else None), excluidas


def _agregar(linhas: list[dict]) -> dict:
    medias, excluidas = {}, {}
    for metrica in METRICAS:
        medias[metrica], excluidas[metrica] = _media([l[metrica] for l in linhas])
    return {"n_teses": len(linhas), "medias": medias, "excluidas": excluidas}


def avaliar(
    teses: list[Tese],
    buscar_ids: Callable[[dict], list[str]],
    rotulos: Callable[[uuid.UUID], tuple[dict[str, int], dict[str, str]]],
) -> dict:
    """Roda a busca de cada tese e calcula as 4 métricas contra os rótulos finais.

    Input:  teses; buscar_ids(estrutura) -> ids dos documentos em ordem de ranking;
            rotulos(tese_id) -> (documento_id -> relevância, documento_id -> stance).
    Returns: {"por_tese": [...], "por_split": {...}, "por_origem": {...},
             "teses_com_erro": [tese_id, ...]}. Cada grupo traz n_teses, medias
             (ignorando None) e excluidas (quantas teses ficaram sem a métrica,
             p.ex. sem nenhum relevante ou porque a busca falhou).
    Uma tese cuja busca falha (ValueError/ValidationError) não derruba o eval:
    avisa em stderr e entra com todas as métricas None (excluída das médias).
    """
    por_tese: list[dict] = []
    teses_com_erro: list[str] = []
    for tese in teses:
        try:
            ranking = buscar_ids(tese.estrutura)
        except (ValueError, ValidationError) as e:
            print(f"Aviso: a busca da tese {tese.id} falhou ({e}); excluída das médias.", file=sys.stderr)
            teses_com_erro.append(str(tese.id))
            por_tese.append({
                "tese_id": str(tese.id), "origem": tese.origem, "tema": tese.tema,
                "split": tese.split, **{m: None for m in METRICAS}, "erro": str(e),
            })
            continue
        ganhos, stances = rotulos(tese.id)
        por_tese.append({
            "tese_id": str(tese.id),
            "origem": tese.origem,
            "tema": tese.tema,
            "split": tese.split,
            "ndcg_10": ndcg_at_k(ranking, ganhos, k=10),
            "recall_20": recall_at_k(ranking, ganhos, k=20),
            "fortalece_10": fracao_fortalece(ranking, ganhos, stances, k=10),
            "nao_julgados_10": fracao_nao_julgados(ranking, ganhos, k=10),
        })

    def agrupar(chave: str) -> dict:
        grupos: dict[str, list[dict]] = {}
        for linha in por_tese:
            grupos.setdefault(linha[chave], []).append(linha)
        return {nome: _agregar(linhas) for nome, linhas in sorted(grupos.items())}

    return {
        "por_tese": por_tese,
        "por_split": agrupar("split"),
        "por_origem": agrupar("origem"),
        "teses_com_erro": teses_com_erro,
    }


# --- relatório e CLI --------------------------------------------------------


def _commit_git() -> str | None:
    try:
        saida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
            check=True, cwd=Path(__file__).resolve().parent.parent,
        )
        return saida.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def gravar_relatorio(relatorio: dict, saida: Path, agora: datetime) -> Path:
    saida.mkdir(parents=True, exist_ok=True)
    caminho = saida / f"{agora:%Y-%m-%d_%H%M%S}_{relatorio['split']}.json"
    caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def _fmt(v: float | None) -> str:
    return "  -  " if v is None else f"{v:.3f}"


def imprimir_tabela(avaliacao: dict) -> None:
    print(f"{'grupo':<22}{'teses':>6}" + "".join(f"{m:>17}" for m in METRICAS))
    for titulo, chave in (("split", "por_split"), ("origem", "por_origem")):
        for nome, g in avaliacao[chave].items():
            celulas = "".join(
                f"{_fmt(g['medias'][m]):>10} (-{g['excluidas'][m]})" for m in METRICAS
            )
            print(f"{titulo + ':' + nome:<22}{g['n_teses']:>6}{celulas}")
    print("(-N) = teses excluídas da média por não terem a métrica")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m avaliacao.eval", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", required=True, choices=("dev", "teste"))
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="diretório dos relatórios")
    args = parser.parse_args(argv)

    from avaliacao.contexto import carregar_dependencias, carregar_store

    store = carregar_store()
    teses = store.listar_teses(args.split)
    if not teses:
        print(f"Aviso: nenhuma tese no split '{args.split}'.", file=sys.stderr)
        avaliacao = avaliar([], lambda e: [], store.rotulos_finais)
    else:
        from query.enrichment.schema import EstruturaArgumentativa
        from query.search.pipeline import buscar

        deps = carregar_dependencias()  # lento: BM25, embedder e reranker
        store = deps.store

        def buscar_ids(estrutura: dict) -> list[str]:
            cards = buscar(
                EstruturaArgumentativa(**estrutura),
                hybrid=deps.hybrid, retriever=deps.retriever, reranker=deps.reranker,
            )
            return [c.id for c in cards]

        avaliacao = avaliar(teses, buscar_ids, store.rotulos_finais)

    agora = datetime.now()
    relatorio = {
        "data": agora.isoformat(timespec="seconds"),
        "split": args.split,
        "commit": _commit_git(),
        "n_teses": len(teses),
        **avaliacao,
    }
    caminho = gravar_relatorio(relatorio, args.saida, agora)

    print(f"split={args.split} commit={relatorio['commit']}")
    imprimir_tabela(avaliacao)
    print(f"Relatório gravado em {caminho}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
