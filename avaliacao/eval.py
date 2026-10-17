"""
Comando `eval` do harness: roda a busca do JuriSight para cada tese do
conjunto-ouro, calcula as métricas de ranking contra os rótulos finais e grava
um relatório JSON por execução.

    python -m avaliacao.eval --split {dev,teste} [--saida data/eval/runs/]

Só lê o banco: não chama a API do Jev.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from avaliacao.metricas import (
    fracao_fortalece,
    fracao_nao_julgados,
    kappa_cohen,
    kappa_ponderado_quadratico,
    ndcg_at_k,
    recall_at_k,
)
from avaliacao.store import Julgamento, Tese

SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "eval" / "runs"
METRICAS = ("ndcg_10", "recall_20", "fortalece_10", "nao_julgados_10")
LIMIAR_APROVACAO_KAPPA = 0.6
ALVO_ACURACIA_CONFIANCA = 0.8


def nome_juiz_atual() -> str:
    """Mesmo nome de `JuizJev().nome`, sem instanciar o cliente do Jev."""
    from avaliacao.juiz import MODELO_PADRAO

    return f"jev:{os.getenv('TYPESAFE_MODEL', MODELO_PADRAO)}"


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
    Returns: {"por_tese": [...], "por_split": {...}, "por_origem": {...}}. Cada
             grupo traz n_teses, medias (ignorando None) e excluidas (quantas
             teses ficaram sem a métrica, p.ex. sem nenhum relevante).
    """
    por_tese: list[dict] = []
    for tese in teses:
        ranking = buscar_ids(tese.estrutura)
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

    return {"por_tese": por_tese, "por_split": agrupar("split"), "por_origem": agrupar("origem")}


# --- concordância e calibração ----------------------------------------------


def concordancia_reteste(julgamentos: list[Julgamento]) -> dict:
    """Concordância do mesmo juiz entre a rodada 1 e a rodada 2.

    Input:  julgamentos de UM só juiz (ValueError se houver mais de um).
    Returns: {n, kappa_relevancia (ponderado quadrático), kappa_stance,
             concordancia_exata}; só entram os pares com as duas rodadas.
             concordancia_exata = fração de pares com relevância E stance iguais.
    """
    if len({j.juiz for j in julgamentos}) > 1:
        raise ValueError("concordancia_reteste espera julgamentos de um único juiz")
    r1 = {j.par_id: j for j in julgamentos if j.rodada == 1}
    r2 = {j.par_id: j for j in julgamentos if j.rodada == 2}
    pares = [p for p in r1 if p in r2]
    a = [r1[p] for p in pares]
    b = [r2[p] for p in pares]
    exatos = sum(1 for x, y in zip(a, b) if x.relevancia == y.relevancia and x.stance == y.stance)
    return {
        "n": len(pares),
        "kappa_relevancia": kappa_ponderado_quadratico([x.relevancia for x in a], [y.relevancia for y in b]),
        "kappa_stance": kappa_cohen([x.stance for x in a], [y.stance for y in b]),
        "concordancia_exata": exatos / len(pares) if pares else None,
    }


def limite_confianca(
    itens: list[tuple[float, bool]], alvo: float = ALVO_ACURACIA_CONFIANCA
) -> tuple[float | None, int]:
    """Menor limite de confiança t tal que a acurácia dos itens com confiança >= t é >= alvo.

    Input:  itens — (confiança, acertou) por par.
    Returns: (t, quantos itens têm confiança >= t); (None, 0) se nenhum limite atinge o alvo.
    """
    for t in sorted({c for c, _ in itens}):
        acima = [acertou for c, acertou in itens if c >= t]
        if sum(acima) / len(acima) >= alvo - 1e-9:
            return t, len(acima)
    return None, 0


def _confianca(j: Julgamento) -> float:
    return min(j.confianca_rel or 0.0, j.confianca_stance or 0.0)


def kappas_calibracao(store) -> dict:
    """Calibração do Jev atual contra a especialista.

    Humano de referência por par: o julgamento humano mais recente (o
    `store.julgamentos` já vem ordenado por criado_em, então é o último da lista).
    Kappas: só os pares `sorteada` com humano e Jev rodada 1. Limite de
    confiança: pares `incerta` com humano e Jev rodada 1 (confiança = min das
    duas; acerto = relevância e stance exatas).
    """
    amostra = store.amostra()
    humano: dict[uuid.UUID, Julgamento] = {}
    for j in store.julgamentos("humano:"):
        humano[j.par_id] = j  # o último sobrescreve: mais recente
    nome = nome_juiz_atual()
    jev = {j.par_id: j for j in store.julgamentos(nome) if j.juiz == nome and j.rodada == 1}

    comuns = [p for p in jev if p in humano]
    sorteada = [p for p in comuns if amostra.get(p) == "sorteada"]
    incerta = [p for p in comuns if amostra.get(p) == "incerta"]

    k_rel = kappa_ponderado_quadratico([humano[p].relevancia for p in sorteada], [jev[p].relevancia for p in sorteada])
    k_stance = kappa_cohen([humano[p].stance for p in sorteada], [jev[p].stance for p in sorteada])
    itens = [
        (_confianca(jev[p]), jev[p].relevancia == humano[p].relevancia and jev[p].stance == humano[p].stance)
        for p in incerta
    ]
    limite, n_acima = limite_confianca(itens)
    return {
        "n_sorteada": len(sorteada),
        "kappa_relevancia": k_rel,
        "kappa_stance": k_stance,
        "aprovado": (
            k_rel is not None and k_stance is not None
            and k_rel >= LIMIAR_APROVACAO_KAPPA and k_stance >= LIMIAR_APROVACAO_KAPPA
        ),
        "n_incerta": len(incerta),
        "limite_confianca": limite,
        "n_acima_limite": n_acima,
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
    from avaliacao.juiz import PERGUNTAS, perguntas_sha

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

    nome = nome_juiz_atual()
    agora = datetime.now()
    relatorio = {
        "data": agora.isoformat(timespec="seconds"),
        "split": args.split,
        "commit": _commit_git(),
        "modelo_jev": nome,
        "perguntas_sha": perguntas_sha(),
        "perguntas": {k: p.model_dump(mode="json") for k, p in PERGUNTAS.items()},
        "n_teses": len(teses),
        **avaliacao,
        "reteste": concordancia_reteste([j for j in store.julgamentos(nome) if j.juiz == nome]),
        "calibracao": kappas_calibracao(store),
    }
    caminho = gravar_relatorio(relatorio, args.saida, agora)

    print(f"split={args.split} commit={relatorio['commit']} jev={nome} perguntas_sha={relatorio['perguntas_sha'][:12]}")
    imprimir_tabela(avaliacao)
    print(f"reteste: {relatorio['reteste']}")
    print(f"calibração: {relatorio['calibracao']}")
    print(f"Relatório gravado em {caminho}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
