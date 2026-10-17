"""Testes do CLI do passo 0 (funções puras; sem Jev, OpenAI nem banco)."""
import csv
import uuid

import pytest

from avaliacao.passo_zero import (
    COLUNAS_CSV,
    escolher_docs,
    escrever_csv,
    confirmar,
    csv_tem_rotulos,
    jev_das_rodadas,
    ler_csv,
    ler_ids_csv,
    comparar,
    preparar,
    resumo_comparacao,
)
from avaliacao.store import Julgamento


def _j(par, juiz, rodada, rel, stance):
    return Julgamento(par_id=par, juiz=juiz, rodada=rodada, relevancia=rel, stance=stance)


def test_resumo_comparacao_valores():
    p = [uuid.uuid4() for _ in range(4)]
    humanos = [_j(p[0], "humano:a", 1, 3, "fortalece"), _j(p[1], "humano:a", 1, 0, "neutro"),
               _j(p[2], "humano:a", 1, 2, "enfraquece"), _j(p[3], "humano:a", 1, 1, "neutro")]
    jev1 = [_j(p[0], "jev:x", 1, 3, "fortalece"), _j(p[1], "jev:x", 1, 0, "neutro"),
            _j(p[2], "jev:x", 1, 2, "fortalece"), _j(p[3], "jev:x", 1, 0, "neutro")]
    jev2 = [_j(p[0], "jev:x", 2, 3, "fortalece"), _j(p[1], "jev:x", 2, 1, "neutro"),
            _j(p[2], "jev:x", 2, 2, "fortalece"), _j(p[3], "jev:x", 2, 0, "neutro")]

    r = resumo_comparacao(humanos, jev1, jev2)

    assert r["n"] == 4
    # relevância: h=[3,0,2,1] j=[3,0,2,0]; soma w_o = 1/9; soma w_e = 48/(9*4) = 12/9 -> 1 - 1/12
    assert r["kappa_relevancia"] == pytest.approx(11 / 12)
    # stance: po=3/4; h: 1 fort, 2 neu, 1 enf; j: 2 fort, 2 neu -> pe=(1*2+2*2)/16=3/8 -> (3/4-3/8)/(5/8)=0.6
    assert r["kappa_stance"] == pytest.approx(0.6)
    # jev1 x jev2: só p1 difere (relevância 0 vs 1) -> 3/4
    assert r["concordancia_rodadas"] == pytest.approx(0.75)
    assert r["matriz_stance"] == {
        "fortalece": {"fortalece": 1},
        "neutro": {"neutro": 2},
        "enfraquece": {"fortalece": 1},
    }


def test_resumo_comparacao_casa_por_par_id():
    a, b, c = (uuid.uuid4() for _ in range(3))
    humanos = [_j(a, "humano:a", 1, 3, "fortalece"), _j(b, "humano:a", 1, 0, "neutro")]
    jev1 = [_j(b, "jev:x", 1, 0, "neutro"), _j(c, "jev:x", 1, 3, "fortalece")]
    jev2 = [_j(c, "jev:x", 2, 3, "fortalece")]

    r = resumo_comparacao(humanos, jev1, jev2)

    assert r["n"] == 1  # só b está em humanos e jev1
    assert r["kappa_relevancia"] is None  # n < 2
    assert r["concordancia_rodadas"] == 1.0  # só c está em jev1 e jev2


def test_resumo_comparacao_vazio():
    r = resumo_comparacao([], [], [])
    assert r["n"] == 0
    assert r["kappa_stance"] is None
    assert r["concordancia_rodadas"] is None
    assert r["matriz_stance"] == {}


def test_csv_nao_vaza_nota_do_jev(tmp_path):
    caminho = tmp_path / "eval" / "passo_zero.csv"
    escrever_csv(caminho, [{"par_id": uuid.uuid4(), "tese": "t", "ementa": "e", "link": "http://x"}])
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        cabecalho = next(csv.reader(f))
    assert cabecalho == ["par_id", "tese", "ementa", "link", "relevancia_alexia", "stance_alexia"]
    assert cabecalho == COLUNAS_CSV


def _csv(tmp_path, linhas):
    caminho = tmp_path / "p.csv"
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUNAS_CSV)
        w.writerows(linhas)
    return caminho


def test_ler_csv_ignora_linhas_nao_preenchidas(tmp_path, capsys):
    ok, sem_rel, sem_stance, ruim_rel, ruim_stance, ruim_id = (str(uuid.uuid4()) for _ in range(6))
    caminho = _csv(tmp_path, [
        [ok, "t", "e", "l", "2", "Fortalece "],
        [sem_rel, "t", "e", "l", "", "neutro"],
        [sem_stance, "t", "e", "l", "1", ""],
        [ruim_rel, "t", "e", "l", "4", "neutro"],
        [ruim_stance, "t", "e", "l", "1", "talvez"],
        ["nao-e-uuid", "t", "e", "l", "1", "neutro"],
    ])

    lidos = ler_csv(caminho)

    assert lidos == [(uuid.UUID(ok), 2, "fortalece")]
    avisos = capsys.readouterr().err
    assert ruim_rel in avisos and ruim_stance in avisos and "nao-e-uuid" in avisos
    assert sem_rel not in avisos  # não preenchida não é erro


def test_escolher_docs_ordem_e_slots():
    ranking_a = [f"a{i}" for i in range(20)]
    ranking_b = [f"b{i}" for i in range(20)]
    teses = [
        {"tema": "horas extras", "ranking": ranking_a},
        {"tema": "dano moral", "ranking": ranking_b},
    ]
    escolhidos = escolher_docs(teses, por_tese=4, seed=42)

    a = escolhidos[0]
    assert a[:2] == ["a0", "a1"]
    assert a[2] in ranking_a[14:20]
    assert a[3] in ("b0", "b1")
    assert len(set(a)) == 4
    assert escolher_docs(teses, 4, 42) == escolhidos  # determinístico
    assert escolher_docs(teses, 2, 42) == [["a0", "a1"], ["b0", "b1"]]


def test_escolher_docs_prefere_tema_diferente_e_tese_unica():
    teses = [
        {"tema": "x", "ranking": [f"a{i}" for i in range(20)]},
        {"tema": "x", "ranking": [f"b{i}" for i in range(20)]},
        {"tema": "y", "ranking": [f"c{i}" for i in range(20)]},
    ]
    escolhidos = escolher_docs(teses, por_tese=4, seed=1)
    assert escolhidos[0][3] in ("c0", "c1")  # única de tema diferente
    assert escolhidos[1][3] in ("c0", "c1")
    assert escolhidos[2][3][0] in "ab"  # c: ambas as outras têm tema diferente

    sozinha = escolher_docs([teses[0]], por_tese=4, seed=1)[0]
    assert len(sozinha) == 3  # sem slot de outra tese


def test_escolher_docs_ranking_curto_nao_duplica():
    teses = [{"tema": "x", "ranking": ["a0", "a1", "a2"]}, {"tema": "x", "ranking": ["a0", "b1"]}]
    escolhidos = escolher_docs(teses, por_tese=4, seed=3)
    assert all(len(set(e)) == len(e) for e in escolhidos)
    assert escolhidos[0][:2] == ["a0", "a1"]


def test_ler_ids_csv_inclui_nao_rotuladas(tmp_path):
    a, b = uuid.uuid4(), uuid.uuid4()
    caminho = _csv(tmp_path, [[a, "t", "e", "l", "2", "neutro"], [b, "t", "e", "l", "", ""],
                              ["lixo", "t", "e", "l", "", ""]])
    assert ler_ids_csv(caminho) == [a, b]


def test_jev_das_rodadas_filtra_pelos_pares_do_csv():
    no_csv, fora = uuid.uuid4(), uuid.uuid4()
    jev = [_j(no_csv, "jev:x", 1, 1, "neutro"), _j(no_csv, "jev:x", 2, 1, "neutro"),
           _j(fora, "jev:x", 1, 3, "fortalece"), _j(fora, "jev:x", 2, 0, "enfraquece")]

    jev1, jev2 = jev_das_rodadas(jev, {no_csv})

    assert [j.par_id for j in jev1] == [no_csv]
    assert [j.par_id for j in jev2] == [no_csv]
    r = resumo_comparacao([], jev1, jev2)
    assert r["n_rodadas"] == 1 and r["concordancia_rodadas"] == 1.0  # o par de fora discorda e não entra


def test_csv_tem_rotulos(tmp_path):
    a = uuid.uuid4()
    assert not csv_tem_rotulos(tmp_path / "nao_existe.csv")
    assert not csv_tem_rotulos(_csv(tmp_path, [[a, "t", "e", "l", "", ""]]))
    assert csv_tem_rotulos(_csv(tmp_path, [[a, "t", "e", "l", "", ""], [a, "t", "e", "l", "1", ""]]))


def test_preparar_recusa_sobrescrever_csv_rotulado(tmp_path, capsys):
    caminho = _csv(tmp_path, [[uuid.uuid4(), "t", "e", "l", "2", "neutro"]])
    assert preparar(1, 2, True, caminho) == 1
    assert "rótulo" in capsys.readouterr().err


def test_comparar_valida_antes_de_conectar(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AVALIACAO_EMAILS", raising=False)
    assert comparar(tmp_path / "nao_existe.csv", "a@b.c") == 2
    assert "CSV" in capsys.readouterr().err
    caminho = _csv(tmp_path, [])
    monkeypatch.setattr("avaliacao.passo_zero._carregar_env", lambda: None)
    assert comparar(caminho, None) == 2
    assert "rotulador" in capsys.readouterr().err


def test_confirmar_trata_eof_como_cancelado(monkeypatch):
    def _eof(_):
        raise EOFError
    monkeypatch.setattr("builtins.input", _eof)
    assert confirmar("?") is False
