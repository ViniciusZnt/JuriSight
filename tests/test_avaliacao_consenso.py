from avaliacao.consenso import rotulo_final

A, B, C = "humano:a@x.invalid", "humano:b@x.invalid", "humano:c@x.invalid"


def test_um_so_humano_vale_o_dele():
    assert rotulo_final([(A, 2, "fortalece")], None) == (2, "fortalece")


def test_sem_julgamento_e_none():
    assert rotulo_final([], None) is None


def test_notas_iguais():
    assert rotulo_final([(A, 3, "fortalece"), (B, 3, "fortalece")], None) == (3, "fortalece")


def test_diferenca_de_um_vale_a_menor():
    assert rotulo_final([(A, 1, "neutro"), (B, 2, "fortalece")], None) == (1, "neutro")


def test_diferenca_de_dois_e_pendente():
    assert rotulo_final([(A, 0, "neutro"), (B, 2, "fortalece")], None) is None


def test_stance_diferente_com_notas_altas_e_pendente():
    assert rotulo_final([(A, 2, "fortalece"), (B, 3, "enfraquece")], None) is None


def test_adjudicador_prevalece_mesmo_com_desacordo():
    julgs = [(A, 0, "neutro"), (B, 3, "fortalece"), (C, 2, "enfraquece")]
    assert rotulo_final(julgs, "  C@X.invalid ") == (2, "enfraquece")


def test_adjudicador_que_nao_julgou_nao_resolve():
    assert rotulo_final([(A, 0, "neutro"), (B, 3, "fortalece")], "c@x.invalid") is None
