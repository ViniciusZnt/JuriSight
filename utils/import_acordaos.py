#!/usr/bin/env python3
"""
Importa acordaos.json (respostas brutas da API Falcão) para o PostgreSQL.

O arquivo é lido em streaming para não carregar 1.4GB na memória de uma vez.
Cada documento passa pelo mesmo parse_document da spider antes de ser inserido.

Uso:
    uv run python utils/import_acordaos.py
    uv run python utils/import_acordaos.py --file /outro/caminho/acordaos.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg
from scraper.spiders.utils.html_parser import parse_document


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)
DEFAULT_FILE = ROOT / "acordaos.json"
BATCH_SIZE   = 200
CHUNK_SIZE   = 512 * 1024  # 512 KB por leitura


# ─── SQL ──────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS documentos (
    id                     SERIAL PRIMARY KEY,
    id_documento           TEXT        UNIQUE NOT NULL,
    tipo_documento         TEXT,
    hierarquia_categoria   INTEGER,
    data_filtro            TEXT,
    numero_processo        TEXT,
    tribunal               TEXT,
    classe_processo        TEXT,
    sigla_classe           TEXT,
    relator                TEXT,
    turma                  TEXT,
    gabinete               TEXT,
    data_julgamento        TEXT,
    data_juntada           TEXT,
    cabecalho              TEXT,
    ementa                 TEXT,
    relatorio              TEXT,
    fundamentacao          TEXT,
    acordao                TEXT,
    votos                  TEXT,
    possui_ementa          BOOLEAN,
    referencia_legislativa TEXT[],
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at             TIMESTAMPTZ NOT NULL
);
"""

_UPSERT = """
INSERT INTO documentos (
    id_documento, tipo_documento, hierarquia_categoria, data_filtro,
    numero_processo, tribunal, classe_processo, sigla_classe,
    relator, turma, gabinete, data_julgamento, data_juntada,
    cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
    possui_ementa, referencia_legislativa, scraped_at
) VALUES (
    %(id_documento)s, %(tipo_documento)s, %(hierarquia_categoria)s, %(data_filtro)s,
    %(numero_processo)s, %(tribunal)s, %(classe_processo)s, %(sigla_classe)s,
    %(relator)s, %(turma)s, %(gabinete)s, %(data_julgamento)s, %(data_juntada)s,
    %(cabecalho)s, %(ementa)s, %(relatorio)s, %(fundamentacao)s, %(acordao)s, %(votos)s,
    %(possui_ementa)s, %(referencia_legislativa)s, %(scraped_at)s
)
ON CONFLICT (id_documento) DO UPDATE SET
    tipo_documento         = EXCLUDED.tipo_documento,
    hierarquia_categoria   = EXCLUDED.hierarquia_categoria,
    data_filtro            = EXCLUDED.data_filtro,
    numero_processo        = EXCLUDED.numero_processo,
    tribunal               = EXCLUDED.tribunal,
    classe_processo        = EXCLUDED.classe_processo,
    sigla_classe           = EXCLUDED.sigla_classe,
    relator                = EXCLUDED.relator,
    turma                  = EXCLUDED.turma,
    gabinete               = EXCLUDED.gabinete,
    data_julgamento        = EXCLUDED.data_julgamento,
    data_juntada           = EXCLUDED.data_juntada,
    cabecalho              = EXCLUDED.cabecalho,
    ementa                 = EXCLUDED.ementa,
    relatorio              = EXCLUDED.relatorio,
    fundamentacao          = EXCLUDED.fundamentacao,
    acordao                = EXCLUDED.acordao,
    votos                  = EXCLUDED.votos,
    possui_ementa          = EXCLUDED.possui_ementa,
    referencia_legislativa = EXCLUDED.referencia_legislativa,
    scraped_at             = EXCLUDED.scraped_at;
"""


# ─── Streaming JSON reader ────────────────────────────────────────────────────

def iter_json_array(filepath: Path):
    """
    Itera sobre os objetos de um array JSON grande sem carregá-lo todo na memória.
    Lê o arquivo em chunks e usa JSONDecoder.raw_decode para extrair objetos.
    """
    decoder = json.JSONDecoder()
    buf = ""

    with open(filepath, encoding="utf-8") as f:
        # Avança até o '[' de abertura do array
        while "[" not in buf:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                return
            buf += chunk
        buf = buf[buf.index("[") + 1 :]

        while True:
            buf = buf.lstrip(" \n\r\t,")

            if buf.startswith("]"):
                return

            # Se o buffer está vazio ou curto, lê mais dados
            if len(buf) < 1024:
                chunk = f.read(CHUNK_SIZE)
                if chunk:
                    buf += chunk

            # Tenta decodificar o próximo objeto; lê mais se incompleto
            while True:
                try:
                    obj, end = decoder.raw_decode(buf)
                    buf = buf[end:]
                    yield obj
                    break
                except json.JSONDecodeError:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        return  # fim do arquivo
                    buf += chunk


# ─── Transformação (mesma lógica de extract_item da spider) ──────────────────

def doc_to_row(raw: dict, scraped_at: datetime) -> dict | None:
    doc_id = raw.get("idDocumentoAcordao", "")
    if not doc_id:
        return None

    parsed   = parse_document(raw.get("ementa", ""), raw.get("textoAcordao", ""))
    sections = parsed["acordao_section"]

    return {
        "id_documento":           doc_id,
        "tipo_documento":         "ACORDAO",
        "hierarquia_categoria":   4,
        # data_filtro = dataJuntada (a spider filtrava por dia de juntada)
        "data_filtro":            raw.get("dataJuntada", ""),
        "numero_processo":        raw.get("numeroProcesso", ""),
        "tribunal":               raw.get("tribunal", ""),
        "classe_processo":        raw.get("classeProcesso", ""),
        "sigla_classe":           raw.get("siglaClasseProcesso", ""),
        "relator":                raw.get("relator", ""),
        "turma":                  raw.get("turma", ""),
        "gabinete":               raw.get("gabinete", ""),
        "data_julgamento":        raw.get("dataJulgamento", ""),
        "data_juntada":           raw.get("dataJuntada", ""),
        "possui_ementa":          raw.get("possuiEmenta", "N") == "S",
        "referencia_legislativa": raw.get("referenciaLegislativa") or [],
        "ementa":                 parsed["ementa"] or sections.get("ementa", ""),
        "cabecalho":              sections.get("cabecalho", ""),
        "relatorio":              sections.get("relatorio", ""),
        "fundamentacao":          sections.get("fundamentacao", ""),
        "acordao":                sections.get("acordao", ""),
        "votos":                  sections.get("votos", ""),
        "scraped_at":             scraped_at,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(filepath: Path) -> None:
    if not filepath.exists():
        print(f"Arquivo não encontrado: {filepath}", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando ao banco: {DATABASE_URL}")
    conn = psycopg.connect(DATABASE_URL)

    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()
    print("Tabela documentos pronta.\n")

    scraped_at = datetime.now(tz=timezone.utc)
    batch: list[dict] = []
    total = inserted = skipped = errors = 0

    def flush(batch: list[dict]) -> tuple[int, int]:
        ok = err = 0
        try:
            with conn.cursor() as cur:
                cur.executemany(_UPSERT, batch)
            conn.commit()
            ok = len(batch)
        except Exception as e:
            conn.rollback()
            print(f"\n  [ERRO no flush] {e}")
            err = len(batch)
        return ok, err

    print(f"Lendo {filepath.name} em streaming...")
    for raw in iter_json_array(filepath):
        total += 1
        row = doc_to_row(raw, scraped_at)

        if row is None:
            skipped += 1
            continue

        batch.append(row)

        if len(batch) >= BATCH_SIZE:
            ok, err = flush(batch)
            inserted += ok
            errors   += err
            batch.clear()

        if total % 1000 == 0:
            pct = inserted / max(total - skipped, 1) * 100
            print(
                f"  {total:>6} lidos | {inserted:>6} inseridos/atualizados "
                f"| {skipped} sem id | {errors} erros  ({pct:.0f}%)",
                end="\r",
            )

    # Flush do restante
    if batch:
        ok, err = flush(batch)
        inserted += ok
        errors   += err

    conn.close()

    print(f"\n\nConcluído.")
    print(f"  Total lido:              {total}")
    print(f"  Inseridos/atualizados:   {inserted}")
    print(f"  Sem id_documento:        {skipped}")
    print(f"  Erros:                   {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa acordaos.json para o PostgreSQL.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help=f"Caminho do JSON (padrão: {DEFAULT_FILE})",
    )
    args = parser.parse_args()
    main(args.file)
