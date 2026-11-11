from query.filtros.expressoes import sem_acento, variantes, tsquery_da_expressao

def test_sem_acento():
    assert sem_acento("Indenização POR Dano") == "indenizacao por dano"

def test_variantes():
    assert variantes("moral") == ["morais", "moral"]
    assert variantes("morais") == ["morais", "moral"]
    assert variantes("dano") == ["dano", "danos"]
    assert variantes("indenizacao") == ["indenizacao", "indenizacaos", "indenizacoes"]
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
