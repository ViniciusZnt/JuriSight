"""Importação da planilha com várias teses num arquivo (aba Julgamento)."""
import shutil
import uuid
from pathlib import Path

import openpyxl
import pytest

from avaliacao import planilha_julgamento as pj
from avaliacao.store import Par, Tese

REAL = Path(pj.__file__).resolve().parent.parent / "docs" / "avaliacao" / "2-julgamento-relevancia-e-stance.xlsx"


class _Store:
    def __init__(self, teses, pares):
        self.teses, self.pares, self.gravados = teses, pares, []

    def listar_teses(self, split=None):
        return list(self.teses)

    def pares_da_tese(self, tese_id):
        return list(self.pares.get(tese_id, []))

    def gravar_julgamento(self, j):
        self.gravados.append(j)


def _arquivo(caminho, linhas):
    wb = openpyxl.Workbook()
    wb.active.title = "Instruções"
    ws = wb.create_sheet("Julgamento")
    ws.append(["Código", "Nº", "Tese", "Processo", "Ementa", "Nota", "Stance", "Comentário", "Nome", "Formação"])
    for n, (par, nota, stance, nome) in enumerate(linhas, start=1):
        ws.append([str(par), n, f"tese {n}", "p", "e", nota, stance, None, nome, "Advogada"])
    wb.save(caminho)
    return caminho


@pytest.fixture
def cenario():
    t1, t2 = uuid.uuid4(), uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    teses = [Tese(t1, {}, "advogado", "x", "dev"), Tese(t2, {}, "sintetica", "y", "teste")]
    return p1, p2, _Store(teses, {t1: [Par(p1, t1, "d1", [])], t2: [Par(p2, t2, "d2", [])]})


def test_grava_pares_de_teses_diferentes_com_o_nome_da_linha(tmp_path, cenario):
    p1, p2, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 3, "fortalece", "  Ana   Silva "), (p2, 1, None, "ana silva")])
    assert pj.importar_arquivo(store, arq) == (2, {})
    assert {(j.par_id, j.juiz, j.rodada, j.relevancia, j.stance) for j in store.gravados} == {
        (p1, "humano:ana silva", 1, 3, "fortalece"), (p2, "humano:ana silva", 1, 1, "neutro")}


def test_nota_sem_nome_e_pulada(tmp_path, cenario):
    p1, p2, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 3, "fortalece", None), (p2, 1, None, "Ana")])
    assert pj.importar_arquivo(store, arq) == (1, {"sem nome": 1})
    assert [j.par_id for j in store.gravados] == [p2]


def test_par_desconhecido_e_ignorado_sem_gravar(tmp_path, cenario):
    p1, _, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 2, "neutro", "Ana"), (uuid.uuid4(), 3, "fortalece", "Ana")])
    gravadas, motivos = pj.importar_arquivo(store, arq)
    assert gravadas == 1 and motivos == {"par fora da tese": 1}
    assert [j.par_id for j in store.gravados] == [p1]


def test_mantem_as_regras_de_linha_invalida(tmp_path, cenario):
    p1, p2, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 2, None, "Ana"), (p2, 9, None, "Ana")])
    assert pj.importar_arquivo(store, arq) == (0, {"stance vazio com nota 2 ou 3": 1, "nota fora de 0 a 3": 1})


def test_arquivo_sem_nenhuma_nota_falha(tmp_path, cenario):
    p1, _, store = cenario
    with pytest.raises(ValueError, match="nenhuma nota"):
        pj.importar_arquivo(store, _arquivo(tmp_path / "j.xlsx", [(p1, None, None, None)]))


def test_avisa_quando_o_arquivo_tem_mais_de_um_nome(tmp_path, cenario, capsys):
    p1, p2, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 1, None, "Ana"), (p2, 1, None, "Ana Silva")])
    pj.importar_arquivo(store, arq)
    erro = capsys.readouterr().err
    assert "ana" in erro and "ana silva" in erro


def test_adjudicacao_nao_aceita_a_planilha_com_varias_teses(tmp_path, cenario):
    p1, _, store = cenario
    arq = _arquivo(tmp_path / "j.xlsx", [(p1, 1, None, "Ana")])
    with pytest.raises(ValueError, match="adjudicação"):
        pj.importar_arquivo(store, arq, rodada=2, adjudicador="adj@x.com")
    assert store.gravados == []


def test_planilha_distribuida_e_lida(tmp_path):
    """A planilha real, preenchida como o avaliador faria, volta pelo importador."""
    p = tmp_path / "real.xlsx"
    shutil.copy(REAL, p)
    wb = openpyxl.load_workbook(p)
    assert wb.sheetnames == ["Instruções", "Julgamento"]
    ws = wb["Julgamento"]
    assert [ws.cell(1, c).value for c in (8, 9, 10)] == [
        "Comentário (opcional)", "Nome de quem preencheu", "Formação/Profissão de quem preencheu"]
    codigos = [uuid.UUID(ws.cell(r, 1).value) for r in range(2, 32)]
    for r in range(2, 32):
        ws.cell(r, 6).value, ws.cell(r, 7).value = 3, "enfraquece"
        ws.cell(r, 9).value, ws.cell(r, 10).value = "Ana", "Advogada"
    wb.save(p)
    t = uuid.uuid4()
    store = _Store([Tese(t, {}, "advogado", "x", "dev")], {t: [Par(c, t, "d", []) for c in codigos]})
    assert pj.importar_arquivo(store, p) == (30, {})
    assert {(j.juiz, j.relevancia, j.stance) for j in store.gravados} == {("humano:ana", 3, "enfraquece")}
