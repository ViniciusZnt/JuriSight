"""Rede de segurança do SQL do scraper: a coleta não tem teste contra banco, então o SQL
atual fica guardado aqui (com os espaços colapsados) e qualquer refatoração tem de gerar o mesmo."""
from scraper.db_writer import _CREATE_TABLE, _UPSERT


def _normalizado(sql: str) -> str:
    return " ".join(sql.split())


CREATE_TABLE_ESPERADO = (
    "CREATE TABLE IF NOT EXISTS documentos ( id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "id_documento TEXT UNIQUE NOT NULL, tipo_documento TEXT, hierarquia_categoria INTEGER, "
    "data_filtro DATE, numero_processo TEXT, tribunal TEXT, classe_processo TEXT, sigla_classe "
    "TEXT, relator TEXT, turma TEXT, gabinete TEXT, data_julgamento DATE, data_juntada DATE, "
    "cabecalho TEXT, ementa TEXT, relatorio TEXT, fundamentacao TEXT, acordao TEXT, votos TEXT, "
    "possui_ementa BOOLEAN, referencia_legislativa TEXT[], provimento TEXT, link_original TEXT, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), scraped_at TIMESTAMPTZ NOT NULL );"
)

UPSERT_ESPERADO = (
    "INSERT INTO documentos ( id_documento, tipo_documento, hierarquia_categoria, data_filtro, "
    "numero_processo, tribunal, classe_processo, sigla_classe, relator, turma, gabinete, "
    "data_julgamento, data_juntada, cabecalho, ementa, relatorio, fundamentacao, acordao, votos, "
    "possui_ementa, referencia_legislativa, provimento, link_original, scraped_at ) VALUES ( "
    "%(id_documento)s, %(tipo_documento)s, %(hierarquia_categoria)s, %(data_filtro)s, "
    "%(numero_processo)s, %(tribunal)s, %(classe_processo)s, %(sigla_classe)s, %(relator)s, "
    "%(turma)s, %(gabinete)s, %(data_julgamento)s, %(data_juntada)s, %(cabecalho)s, %(ementa)s, "
    "%(relatorio)s, %(fundamentacao)s, %(acordao)s, %(votos)s, %(possui_ementa)s, "
    "%(referencia_legislativa)s, %(provimento)s, %(link_original)s, %(scraped_at)s ) ON CONFLICT "
    "(id_documento) DO UPDATE SET tipo_documento = EXCLUDED.tipo_documento, hierarquia_categoria "
    "= EXCLUDED.hierarquia_categoria, data_filtro = EXCLUDED.data_filtro, numero_processo = "
    "EXCLUDED.numero_processo, tribunal = EXCLUDED.tribunal, classe_processo = "
    "EXCLUDED.classe_processo, sigla_classe = EXCLUDED.sigla_classe, relator = EXCLUDED.relator, "
    "turma = EXCLUDED.turma, gabinete = EXCLUDED.gabinete, data_julgamento = "
    "EXCLUDED.data_julgamento, data_juntada = EXCLUDED.data_juntada, cabecalho = "
    "EXCLUDED.cabecalho, ementa = EXCLUDED.ementa, relatorio = EXCLUDED.relatorio, fundamentacao "
    "= EXCLUDED.fundamentacao, acordao = EXCLUDED.acordao, votos = EXCLUDED.votos, possui_ementa "
    "= EXCLUDED.possui_ementa, referencia_legislativa = EXCLUDED.referencia_legislativa, "
    "provimento = EXCLUDED.provimento, link_original = EXCLUDED.link_original, scraped_at = "
    "EXCLUDED.scraped_at;"
)


def test_create_table_nao_mudou():
    assert _normalizado(_CREATE_TABLE) == CREATE_TABLE_ESPERADO


def test_upsert_nao_mudou():
    assert _normalizado(_UPSERT) == UPSERT_ESPERADO
