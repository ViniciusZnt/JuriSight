"""
CLI do provimento com o Jev. Subcomandos: `classificar` (backfill retomável),
`comparar` (regex x Jev, gera CSV de divergências), `conferir` (resume o CSV preenchido)
e `aplicar` (escreve o Jev em `documentos.provimento`, só com --confirmar).
Ver docs/superpowers/specs/2026-10-20-provimento-jev-design.md.

Uso: uv run python -m scraper.provimento_jev_cli classificar [--limite N] [--sim]
     uv run python -m scraper.provimento_jev_cli comparar [--amostra 100] [--csv CAMINHO]
     uv run python -m scraper.provimento_jev_cli conferir [--csv CAMINHO]
     uv run python -m scraper.provimento_jev_cli aplicar [--confianca-min 0.8] [--confirmar]
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from typesafe_sdk import TypeSafeError

from avaliacao.passo_zero import confirmar
from scraper.provimento_jev import (
    MODELO_PADRAO,
    TOKENS_POR_ACORDAO,
    ClassificadorJev,
    validar_modelo,
    favorece_por_regra,
    para_provimento,
    perguntas_sha,
)

ROOT = Path(__file__).resolve().parent.parent
CSV_DIVERGENCIAS = ROOT / "data" / "eval" / "provimento_divergencias.csv"
COLUNAS_DIVERGENCIAS = [
    "documento_id", "link", "trecho_dispositivo", "regex",
    "jev_resultado", "jev_recorrente", "jev_favorece", "confianca", "quem_acertou",
]
VALORES_QUEM_ACERTOU = ("jev", "regex", "ambos", "nenhum")
logger = logging.getLogger(__name__)


def classificar_pendentes(
    store, classificador, itens: list, perguntas_sha: str, max_workers: int = 8
) -> tuple[int, int]:
    """Classifica `itens` em paralelo e grava cada sucesso (na thread principal).
    Devolve `(ok, falhas)`; falha de um item não derruba o lote."""

    def _um(item):
        try:
            return item, classificador.classificar(item.acordao, item.ementa), None
        except (TypeSafeError, ValueError) as e:
            return item, None, e

    ok = falhas = 0
    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futuros = [pool.submit(_um, item) for item in itens]
        # as_completed grava cada resultado pago assim que chega, sem esperar item lento.
        for futuro in as_completed(futuros):
            item, c, erro = futuro.result()
            if erro is not None:
                falhas += 1
                logger.warning("Falha em %s: %s", item.documento_id, erro)
                continue
            store.gravar(
                item.documento_id, c, item.provimento_regex,
                modelo=classificador.model, perguntas_sha=perguntas_sha,
            )
            ok += 1
    except BaseException:
        # Não espera chamadas pagas ainda enfileiradas (inclui Ctrl-C).
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return ok, falhas


def resumo(linhas: list) -> dict:
    """Compara a regex com o Jev. Chaves: `n` (linhas); `matriz`
    (`provimento_regex` -> `para_provimento(resultado).value` -> contagem);
    `concordancia` (fração em que os dois coincidem); `distribuicao`
    (`resultado`/`recorrente`/`favorece` -> contagens); `coerencia_favorece`
    (`n` = casos em que a regra opina, `concordam` = fração em que o Jev concorda)."""
    matriz: dict[str, dict[str, int]] = {}
    iguais = 0
    for l in linhas:
        jev = para_provimento(l.resultado).value
        linha = matriz.setdefault(l.provimento_regex, {})
        linha[jev] = linha.get(jev, 0) + 1
        iguais += l.provimento_regex == jev
    opinam = concordam = 0
    for l in linhas:
        esperado = favorece_por_regra(l.resultado, l.recorrente)
        if esperado is not None:
            opinam += 1
            concordam += esperado == l.favorece
    return {
        "n": len(linhas),
        "matriz": matriz,
        "concordancia": iguais / len(linhas) if linhas else 0.0,
        "distribuicao": {
            "resultado": dict(Counter(l.resultado for l in linhas)),
            "recorrente": dict(Counter(l.recorrente for l in linhas)),
            "favorece": dict(Counter(l.favorece for l in linhas)),
        },
        "coerencia_favorece": {
            "n": opinam, "concordam": concordam / opinam if opinam else 0.0,
        },
    }


def divergencias(linhas: list, n: int, seed: int) -> list:
    """Sorteia até `n` linhas em que a regex diverge do Jev (ordem estável por id)."""
    div = sorted(
        (l for l in linhas if l.provimento_regex != para_provimento(l.resultado).value),
        key=lambda l: l.documento_id,
    )
    return random.Random(seed).sample(div, min(n, len(div)))


def escrever_csv_divergencias(caminho: Path, linhas: list, trechos: dict) -> None:
    """CSV para conferência manual (utf-8 com BOM, como o do passo 0);
    `quem_acertou` fica vazio para o usuário preencher."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_DIVERGENCIAS)
        w.writeheader()
        for l in linhas:
            link, trecho = trechos.get(l.documento_id, (None, ""))
            w.writerow({
                "documento_id": l.documento_id,
                "link": link or "",
                "trecho_dispositivo": trecho,
                "regex": l.provimento_regex,
                "jev_resultado": l.resultado,
                "jev_recorrente": l.recorrente,
                "jev_favorece": l.favorece,
                "confianca": l.confianca_resultado,
                "quem_acertou": "",
            })


def _ler_csv(caminho: Path) -> tuple[list[str], list[dict]]:
    """Lê o CSV aceitando `,` ou `;` (Excel pt-BR salva com `;`). Devolve (cabeçalho, linhas)."""
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        amostra = f.read(4096)
        f.seek(0)
        try:
            delimitador = csv.Sniffer().sniff(amostra, delimiters=",;").delimiter
        except csv.Error:
            delimitador = ","
        leitor = csv.DictReader(f, delimiter=delimitador)
        linhas = list(leitor)
        return list(leitor.fieldnames or []), linhas


def csv_conferido(caminho: Path) -> bool:
    """True se o arquivo existe e alguma linha tem `quem_acertou` preenchido.
    Arquivo sem a coluna também é True: é melhor recusar do que apagar a conferência."""
    if not Path(caminho).exists():
        return False
    cabecalho, linhas = _ler_csv(caminho)
    if "quem_acertou" not in cabecalho:
        return True
    return any((l.get("quem_acertou") or "").strip() for l in linhas)


def resumo_conferencia(caminho: Path) -> dict:
    """Conta `jev`, `regex`, `ambos`, `nenhum`; vazios são ignorados e valores
    desconhecidos são avisados em stderr e pulados. Sem a coluna `quem_acertou`,
    levanta ValueError."""
    cont = dict.fromkeys(VALORES_QUEM_ACERTOU, 0)
    cabecalho, linhas = _ler_csv(caminho)
    if "quem_acertou" not in cabecalho:
        raise ValueError(
            f"{caminho} não tem a coluna 'quem_acertou' (separador ',' ou ';'); "
            "confira o arquivo ou rode `comparar` de novo."
        )
    for l in linhas:
        v = (l.get("quem_acertou") or "").strip().lower()
        if not v:
            continue
        if v in cont:
            cont[v] += 1
        else:
            print(f"Valor inválido em {l.get('documento_id')}: {v!r} (ignorado)", file=sys.stderr)
    return cont


def _construir_store():
    from dotenv import load_dotenv

    from scraper.provimento_jev_db import ProvimentoJevStore, ensure_schema

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida (veja o .env)")
    ensure_schema(url)
    return ProvimentoJevStore(url)


def _positivo(valor: str) -> int:
    n = int(valor)
    if n <= 0:
        raise argparse.ArgumentTypeError("deve ser > 0")
    return n


def _cmd_classificar(args, store, classificador) -> int:
    # O cliente real só é criado depois da confirmação.
    modelo = classificador.model if classificador else os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    sha = perguntas_sha()
    n = store.contar_pendentes(modelo, sha)
    if args.limite is not None:
        n = min(n, args.limite)
    print(f"Modelo: {modelo}")
    print(f"perguntas_sha: {sha}")
    print(f"Pendentes: {n}")
    print(f"Sem texto (ignorados): {store.contar_sem_texto()}")
    print(f"Estimativa: {n * TOKENS_POR_ACORDAO:,} tokens ({n} × {TOKENS_POR_ACORDAO})")
    if not args.sim and not confirmar("Chamar o Jev (custo)? [s/N] "):
        print("Cancelado.")
        return 1
    classificador = classificador or ClassificadorJev()

    ok = falhas = tentados = 0
    cursor = None
    while args.limite is None or tentados < args.limite:
        restante = args.lote if args.limite is None else min(args.lote, args.limite - tentados)
        itens = store.pendentes(modelo, sha, limite=restante, apos_id=cursor)
        if not itens:
            break
        o, f = classificar_pendentes(store, classificador, itens, sha, args.max_workers)
        ok, falhas, tentados = ok + o, falhas + f, tentados + len(itens)
        cursor = itens[-1].documento_id  # item que sempre falha não volta
        print(f"  {tentados} tentados (ok={ok}, falhas={falhas})")
    print(f"ok={ok} falhas={falhas}")
    return 1 if falhas else 0


def _cmd_comparar(args, store) -> int:
    if csv_conferido(args.csv):
        print(f"{args.csv} já tem 'quem_acertou' preenchido; não será sobrescrito.")
        return 1
    modelo = os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    linhas = store.linhas(modelo, perguntas_sha())
    if not linhas:
        print(f"Nenhuma classificação para {modelo}; rode `classificar` primeiro.")
        return 1
    r = resumo(linhas)
    print(f"Linhas: {r['n']}  concordância regex x Jev: {r['concordancia']:.1%}")
    for regex, jev in sorted(r["matriz"].items()):
        print(f"  regex={regex or '(vazio)'}: {jev}")
    print(f"Distribuição: {r['distribuicao']}")
    c = r["coerencia_favorece"]
    print(f"Coerência de favorece (n={c['n']}): {c['concordam']:.1%}")
    amostra = divergencias(linhas, args.amostra, int(os.getenv("AVALIACAO_SEED", "42")))
    trechos = store.trechos([l.documento_id for l in amostra])
    escrever_csv_divergencias(args.csv, amostra, trechos)
    print(f"{len(amostra)} divergências escritas em {args.csv}")
    return 0


def mudancas(linhas: list, confianca_min: float) -> list[tuple[str, str, str]]:
    """`(documento_id, atual, novo)` onde a confiança atinge o mínimo e o valor muda."""
    r = []
    for l in linhas:
        novo = para_provimento(l.resultado).value
        if l.confianca_resultado >= confianca_min and novo != l.provimento_atual:
            r.append((l.documento_id, l.provimento_atual, novo))
    return r


def _cmd_aplicar(args, store) -> int:
    modelo = os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    linhas = store.linhas(modelo, perguntas_sha())
    if not linhas:
        print(f"Nenhuma classificação para {modelo}; rode `classificar` primeiro.")
        return 1
    muda = mudancas(linhas, args.confianca_min)
    abaixo = [l for l in linhas if l.confianca_resultado < args.confianca_min]
    abaixo_muda = sum(para_provimento(l.resultado).value != l.provimento_atual for l in abaixo)
    for (atual, novo), n in sorted(Counter((a, n) for _, a, n in muda).items()):
        print(f"{atual or '(vazio)'} → {novo}: {n}")
    print(f"Mudanças: {len(muda)} de {len(linhas)} linhas")
    limite = args.confianca_min
    print(f"Linhas abaixo do limite e mudariam: {abaixo_muda} (confiança < {limite})")
    print(f"Linhas abaixo do limite sem mudança: {len(abaixo) - abaixo_muda} (confiança < {limite})")
    if not args.confirmar:
        print("Nada foi escrito; use --confirmar para aplicar.")
        return 0
    mudou = store.aplicar([(d, novo) for d, _, novo in muda])
    print(f"Linhas alteradas em documentos.provimento: {mudou}")
    print("Para restaurar a regex: uv run python utils/reclassify.py")
    return 0


def _fracao(valor: str) -> float:
    x = float(valor)
    if not 0.0 <= x <= 1.0:
        raise argparse.ArgumentTypeError("deve estar entre 0 e 1")
    return x


def _cmd_conferir(args) -> int:
    if not Path(args.csv).exists():
        print(f"CSV não encontrado: {args.csv} (rode `comparar` antes).")
        return 2
    try:
        cont = resumo_conferencia(args.csv)
    except ValueError as e:
        print(e)
        return 2
    total = sum(cont.values())
    print(f"Conferidas: {total}")
    for k, v in cont.items():
        print(f"  {k}: {v}")
    return 0


def main(argv: list[str] | None = None, *, store=None, classificador=None) -> int:
    parser = argparse.ArgumentParser(prog="provimento_jev_cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("classificar", help="backfill retomável com o Jev")
    p.add_argument("--limite", type=_positivo, default=None, help="teto de documentos tentados")
    p.add_argument("--lote", type=_positivo, default=500)
    p.add_argument("--max-workers", type=_positivo, default=8)
    p.add_argument("--sim", action="store_true", help="pula a confirmação")
    p = sub.add_parser("comparar", help="regex x Jev; gera CSV de divergências")
    p.add_argument("--amostra", type=_positivo, default=100)
    p.add_argument("--csv", type=Path, default=CSV_DIVERGENCIAS)
    p = sub.add_parser("conferir", help="resume o CSV de divergências preenchido")
    p.add_argument("--csv", type=Path, default=CSV_DIVERGENCIAS)
    p = sub.add_parser("aplicar", help="escreve o provimento do Jev em documentos (só com --confirmar)")
    p.add_argument("--confianca-min", type=_fracao, default=0.8)
    p.add_argument("--confirmar", action="store_true", help="grava de fato")
    args = parser.parse_args(argv)

    if args.comando == "conferir":
        return _cmd_conferir(args)
    try:
        validar_modelo(os.getenv("TYPESAFE_MODEL", MODELO_PADRAO))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    store = store or _construir_store()
    if args.comando == "comparar":
        return _cmd_comparar(args, store)
    if args.comando == "aplicar":
        return _cmd_aplicar(args, store)

    if args.comando == "classificar":
        return _cmd_classificar(args, store, classificador)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
