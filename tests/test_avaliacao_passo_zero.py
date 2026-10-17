"""Testes do CLI do passo 0 (funções puras; sem Jev, OpenAI nem banco)."""
import csv
import uuid
from types import SimpleNamespace

import pytest

from avaliacao.passo_zero import (
    COLUNAS_CSV,
    escolher_docs,
    texto_tese,
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
    escrever_csv(caminho, [{"par_id": uuid.uuid4(), "tese": "t", "ementa": "e",
                            "fundamentacao_inicio": "f", "link": "http://x"}])
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        cabecalho = next(csv.reader(f))
    assert cabecalho == [
        "par_id", "tese", "ementa", "fundamentacao_inicio", "link",
        "relevancia_alexia", "stance_alexia",
    ]
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
        [ok, "t", "e", "f", "l", "2", "Fortalece "],
        [sem_rel, "t", "e", "f", "l", "", "neutro"],
        [sem_stance, "t", "e", "f", "l", "1", ""],
        [ruim_rel, "t", "e", "f", "l", "4", "neutro"],
        [ruim_stance, "t", "e", "f", "l", "1", "talvez"],
        ["nao-e-uuid", "t", "e", "f", "l", "1", "neutro"],
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
    caminho = _csv(tmp_path, [[a, "t", "e", "f", "l", "2", "neutro"], [b, "t", "e", "f", "l", "", ""],
                              ["lixo", "t", "e", "f", "l", "", ""]])
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
    assert not csv_tem_rotulos(_csv(tmp_path, [[a, "t", "e", "f", "l", "", ""]]))
    assert csv_tem_rotulos(_csv(tmp_path, [[a, "t", "e", "f", "l", "", ""], [a, "t", "e", "f", "l", "1", ""]]))


def test_preparar_recusa_sobrescrever_csv_rotulado(tmp_path, capsys):
    caminho = _csv(tmp_path, [[uuid.uuid4(), "t", "e", "f", "l", "2", "neutro"]])
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


def test_texto_tese_traz_pedido_tese_e_normas():
    dados = {
        "pedido_principal": "adicional de insalubridade",
        "tese_central": "EPI sem fiscalização não elide a insalubridade.",
        "normas": ["NR-15", "Súmula 289 do TST"],
        "violacoes": ["ignorado"],
    }
    assert texto_tese(dados) == (
        "Pedido: adicional de insalubridade | Tese: EPI sem fiscalização não elide a "
        "insalubridade. | Normas: NR-15; Súmula 289 do TST"
    )
    assert texto_tese({"tese_central": "só a tese", "normas": []}) == "Tese: só a tese"
    assert texto_tese({}) == ""


class _StoreFalso:
    def __init__(self, teses=()):
        self._teses = list(teses)
        self.criadas = []
        self.julgados = []

    def listar_teses(self, split=None):
        return list(self._teses)

    def criar_tese(self, estrutura, origem, tema, split, documento_origem_id=None):
        from avaliacao.store import Tese

        tese = Tese(uuid.uuid4(), estrutura, origem, tema, split, documento_origem_id)
        self.criadas.append(tese)
        return tese

    def adicionar_pares(self, tese_id, docs):
        from avaliacao.store import Par

        return [Par(uuid.uuid4(), tese_id, d, c) for d, c in docs.items()]

    def gravar_julgamento(self, j):
        self.julgados.append(j)


def _preparar_com_fakes(monkeypatch, tmp_path, store, acordaos, n_teses=2, por_tese=2, gerar=None):
    """Roda `preparar` sem rede: troca dependências e etapas pagas por fakes."""
    from avaliacao.temas import TEMAS
    from query.enrichment.schema import EstruturaArgumentativa

    pedidos_sorteio = []
    uuids = {a.id_documento: f"uuid-{a.id_documento}" for a in acordaos}
    fundamentacao = "F" * 3500
    docs = {
        f"uuid-{a.id_documento}": SimpleNamespace(
            ementa=f"ementa {a.id_documento}", fundamentacao=fundamentacao,
            link_original=f"http://x/{a.id_documento}",
        )
        for a in acordaos
    }
    retriever = SimpleNamespace(fetch=lambda ids: {i: docs[i] for i in ids if i in docs})
    deps = SimpleNamespace(
        database_url="postgresql://x", hybrid=None, retriever=retriever, reranker=None, store=store,
    )

    def _sortear(url, n, seed):
        pedidos_sorteio.append(n)
        return acordaos

    monkeypatch.setattr("avaliacao.contexto.carregar_dependencias", lambda: deps)
    monkeypatch.setattr("typesafe_sdk.TypeSafeClient", lambda: object())
    monkeypatch.setattr("avaliacao.juiz.JuizJev", lambda client: SimpleNamespace(nome="jev:x"))
    monkeypatch.setattr("avaliacao.juiz.julgar_lote", lambda juiz, itens, rodada, grava: len(itens))
    monkeypatch.setattr("avaliacao.geracao.sortear_acordaos", _sortear)
    monkeypatch.setattr(
        "avaliacao.geracao.gerar_tese",
        gerar or (lambda acordao, lado: EstruturaArgumentativa(
            pedido_principal=f"pedido {acordao.id_documento}", tese_central=f"tese {acordao.id_documento}",
            normas=["NR-15", "CLT art. 192"],
        )),
    )
    monkeypatch.setattr("avaliacao.temas.atribuir_tema", lambda dados, client=None: TEMAS[0])
    monkeypatch.setattr("avaliacao.passo_zero.uuids_origem", lambda url, a: uuids)
    monkeypatch.setattr(
        "query.search.pipeline.buscar",
        lambda estrutura, **kw: [SimpleNamespace(id=i) for i in docs],
    )
    caminho = tmp_path / "p.csv"
    codigo = preparar(n_teses, por_tese, True, caminho)
    return codigo, caminho, pedidos_sorteio, fundamentacao


def _acordao(id_, provimento):
    return SimpleNamespace(id_documento=id_, provimento=provimento)


def test_preparar_pula_acordao_ja_usado_e_sobreamostra(monkeypatch, tmp_path):
    from avaliacao.store import Tese

    ja_tem_tese = Tese(uuid.uuid4(), {}, "sintetica", "t", "dev", documento_origem_id="uuid-A")
    store = _StoreFalso([ja_tem_tese])
    acordaos = [_acordao("A", "APROVADO"), _acordao("B", "APROVADO"),
                _acordao("C", "NEGADO"), _acordao("D", "NEGADO")]

    codigo, caminho, pedidos, fundamentacao = _preparar_com_fakes(
        monkeypatch, tmp_path, store, acordaos, n_teses=2
    )

    assert codigo == 0
    assert pedidos == [1 + 2 * 2]  # sobreamostra: os já usados mais 2x as pedidas
    assert [t.documento_origem_id for t in store.criadas] == ["uuid-B", "uuid-C"]
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert list(linhas[0]) == COLUNAS_CSV
    assert len(linhas) == 4
    for linha in linhas:
        assert linha["tese"].startswith("Pedido: pedido ") and "| Normas: NR-15; CLT art. 192" in linha["tese"]
        assert linha["fundamentacao_inicio"] == fundamentacao[:3000]
        assert linha["relevancia_alexia"] == "" and linha["stance_alexia"] == ""


def test_preparar_tenta_proximo_candidato_quando_um_falha(monkeypatch, tmp_path):
    from query.enrichment.schema import EstruturaArgumentativa

    store = _StoreFalso()
    acordaos = [_acordao("B", "APROVADO"), _acordao("C", "NEGADO"), _acordao("D", "APROVADO")]

    def _gerar(acordao, lado):
        if acordao.id_documento == "B":
            raise RuntimeError("openai fora")
        return EstruturaArgumentativa(tese_central=f"tese {acordao.id_documento}")

    codigo, _, _, _ = _preparar_com_fakes(monkeypatch, tmp_path, store, acordaos, n_teses=1, gerar=_gerar)

    assert codigo == 0
    assert [t.documento_origem_id for t in store.criadas] == ["uuid-C"]  # B falhou: segue para o próximo candidato


def test_comparar_normaliza_email_do_rotulador(monkeypatch, tmp_path):
    par = uuid.uuid4()
    caminho = _csv(tmp_path, [[par, "t", "e", "f", "l", "2", "neutro"]])

    class _Store:
        def __init__(self):
            self.gravados = []

        def julgamentos(self, prefixo):
            return [_j(par, "jev:x", 1, 2, "neutro"), _j(par, "jev:x", 2, 2, "neutro")]

        def gravar_julgamento(self, j):
            self.gravados.append(j)

    store = _Store()
    monkeypatch.setattr("avaliacao.passo_zero._carregar_env", lambda: None)
    monkeypatch.setattr("avaliacao.contexto.carregar_store", lambda: store)

    assert comparar(caminho, "  Alexia@Escritorio.COM ") == 0
    monkeypatch.setenv("AVALIACAO_EMAILS", " Outra@X.com , b@y.com")
    assert comparar(caminho, None) == 0

    assert [h.juiz for h in store.gravados] == ["humano:alexia@escritorio.com", "humano:outra@x.com"]
