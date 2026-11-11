import pytest
from query.filtros.expressoes import sem_acento, variantes, tsquery_da_expressao

def test_sem_acento():
    assert sem_acento("Indenização POR Dano") == "indenizacao por dano"

def test_variantes():
    assert variantes("moral") == ["morais", "moral"]
    assert variantes("morais") == ["morais", "moral"]
    assert variantes("dano") == ["dano", "danos"]
    assert variantes("indenizacao") == ["indenizacaes", "indenizacao", "indenizacaos", "indenizacoes"]
    assert variantes("indenizacoes") == ["indenizacao", "indenizacaos", "indenizacoes"]
    assert variantes("trabalhadores") == ["trabalhador", "trabalhadores"]
    assert variantes("coletivos") == ["coletivo", "coletivos"]
    assert variantes("de") == ["de"]

def test_variantes_singular_ou_plural_por_regra_especifica():
    assert "orgaos" in variantes("orgao")
    assert "cidadaos" in variantes("cidadao")
    assert "lei" in variantes("leis")
    assert "papel" in variantes("papeis")
    assert "orgao" in variantes("orgaos")

@pytest.mark.parametrize("palavra,variante", [
    ("viagem", "viagens"), ("viagens", "viagem"), ("ordem", "ordens"), ("vantagens", "vantagem"),
    ("civil", "civis"), ("civis", "civil"), ("lencol", "lencois"), ("lencois", "lencol"),
    ("mes", "meses"), ("meses", "mes"), ("teses", "tese"), ("partes", "parte"),
    ("pao", "paes"), ("paes", "pao"), ("taxis", "taxi"),
])
def test_variantes_plurais_irregulares(palavra, variante):
    assert variante in variantes(palavra)


@pytest.mark.parametrize("conectivo,plural", [
    ("do", "dos"), ("da", "das"), ("no", "nos"), ("na", "nas"), ("ao", "aos"), ("o", "os"), ("a", "as"),
])
def test_conectivos_com_plural(conectivo, plural):
    assert variantes(conectivo) == variantes(plural) == sorted([conectivo, plural])


def test_conectivo_sem_plural_fica_sozinho():
    assert variantes("de") == ["de"] and variantes("por") == ["por"]


def test_tsquery_conectivo_casa_plural():
    assert tsquery_da_expressao("responsabilidade do empregador") == \
        "(responsabilidade | responsabilidades) <-> (do | dos) <-> (empregador | empregadores)"


def test_tsquery_hifen_e_ponto_entre_digitos():
    # o texto indexado troca hífen por espaço e tira o ponto entre dígitos (query/filtros/preparar.py)
    assert tsquery_da_expressao("auxílio-doença") == "(auxilio | auxilios) <-> (doenca | doencas)"
    assert tsquery_da_expressao("Lei 13.467") == "(lei | leis) <-> 13467"
    assert tsquery_da_expressao("R$ 1.000,00").endswith("<-> 1000 <-> 00")


def test_variantes_token_numerico_sem_variante():
    assert variantes("2020") == ["2020"]

def test_tsquery_frase_com_plural():
    assert tsquery_da_expressao("Dano Moral Coletivo") == "(dano | danos) <-> (morais | moral) <-> (coletivo | coletivos)"

def test_tsquery_mantem_conectivo_na_sequencia():
    assert tsquery_da_expressao("adicional de insalubridade") == "(adicionais | adicional) <-> de <-> (insalubridade | insalubridades)"

def test_tsquery_ignora_caracteres_especiais_e_vazio():
    assert tsquery_da_expressao("dano & moral | (coletivo)!") == tsquery_da_expressao("dano moral coletivo")
    assert tsquery_da_expressao("  ") is None
    assert tsquery_da_expressao("de da") is None   # só conectivos
    assert tsquery_da_expressao("':*") is None
