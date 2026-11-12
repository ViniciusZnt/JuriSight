import pytest
from query.filtros.dispositivos import niveis, eh_dispositivo, rotulo, codigo_de_texto, tokens_da_busca, codigos_do_texto

@pytest.mark.parametrize("codigo,esperado", [
    ("b_ii_art_10_adct", ["b_ii_art_10_adct", "ii_art_10_adct", "art_10_adct"]),
    ("prgf_2_art_791_clt", ["prgf_2_art_791_clt", "art_791_clt"]),
    ("prgf_unico_art_456_clt", ["prgf_unico_art_456_clt", "art_456_clt"]),
    ("caput_art_60_clt", ["caput_art_60_clt", "art_60_clt"]),
    ("vi_sumula_85_tst", ["vi_sumula_85_tst", "sumula_85_tst"]),
    ("art_15_clt", ["art_15_clt"]),
    ("prgf_5_art_28_lei_8078_90", ["prgf_5_art_28_lei_8078_90", "art_28_lei_8078_90"]),
    ("trt9", []), ("adct", []),
])
def test_niveis(codigo, esperado):
    assert niveis(codigo) == esperado

def test_eh_dispositivo():
    assert eh_dispositivo("oj_394_sdi1_tst") and eh_dispositivo("lei_13467_17") and eh_dispositivo("convencao_155_oit")
    assert not eh_dispositivo("trt9") and not eh_dispositivo("clt")

@pytest.mark.parametrize("codigo,esperado", [
    ("art_15_clt", "CLT art. 15"),
    ("b_ii_art_10_adct", "ADCT art. 10, II, b"),
    ("prgf_2_art_791_clt", "CLT art. 791, § 2º"),
    ("prgf_unico_art_456_clt", "CLT art. 456, parágrafo único"),
    ("caput_art_60_clt", "CLT art. 60, caput"),
    ("art_186_ccb", "CC art. 186"),
    ("sumula_85_tst", "Súmula 85 do TST"),
    ("vi_sumula_85_tst", "Súmula 85 do TST, VI"),
    ("oj_394_sdi1_tst", "OJ 394 da SDI-1 do TST"),
    ("oj_394_tst", "OJ 394 do TST"),
    ("convencao_155_oit", "Convenção 155 da OIT"),
    ("lei_13467_17", "Lei 13.467/17"),
    ("art_28_lei_8078_90", "Lei 8.078/90 art. 28"),
    ("art_97_ri_trt9", "RI TRT9 art. 97"),
    ("prgf_6_art_11_ri_trt9", "RI TRT9 art. 11, § 6º"),
    ("algo_estranho", "algo_estranho"),
    ("lv_art_5_cf", "CF art. 5, LV"),
    ("lxxiv_art_5_cf", "CF art. 5, LXXIV"),
    ("xl_art_7_cf", "CF art. 7, XL"),
    ("xc_art_1_cf", "CF art. 1, XC"),
])
def test_rotulo(codigo, esperado):
    assert rotulo(codigo) == esperado

@pytest.mark.parametrize("texto,esperado", [
    ("CLT art. 192", "art_192_clt"),
    ("art. 192 da CLT", "art_192_clt"),
    ("Art. 5º, V, da CF", "v_art_5_cf"),
    ("ADCT art. 10, II, b", "b_ii_art_10_adct"),
    ("CLT art. 791, § 2º", "prgf_2_art_791_clt"),
    ("CLT art. 456, parágrafo único", "prgf_unico_art_456_clt"),
    ("Súmula 85 do TST", "sumula_85_tst"),
    ("OJ 394 da SDI-1 do TST", "oj_394_sdi1_tst"),
    ("Lei 8.078/90, art. 28, § 5º", "prgf_5_art_28_lei_8078_90"),
    ("CC art. 186", "art_186_ccb"),
    ("art. 186", None),        # sem lei: não converte (spec: conversão conservadora)
    ("NR-15", "nr_15"),
    ("Súmula 85, item VI, do TST", "vi_sumula_85_tst"),
    ("CLT art. 192 e art. 193", None),
    ("art. 5 7 CLT", None),
    ("Súmula 85 do TST foo", None),
    ("", None),
    ("art. 5º, LV, da CF", "lv_art_5_cf"),
    ("art. 5º, LXXIV, da CF", "lxxiv_art_5_cf"),
    ("Súmula nº 85 do TST", "sumula_85_tst"),
    ("Súmula n. 85 do TST", "sumula_85_tst"),
    ("Lei nº 13.467/2017", "lei_13467_17"),
    ("Lei 13.467/17", "lei_13467_17"),
    ("Lei nº 8.078/1990, art. 28", "art_28_lei_8078_90"),
    ("art. 7º, XXIX, da CF/88", "xxix_art_7_cf"),
    ("CF/1988, art. 7º", "art_7_cf"),
    ("OJ 394 da SBDI-1 do TST", "oj_394_sdi1_tst"),
    ("OJ nº 394 da SDI1 do TST", "oj_394_sdi1_tst"),
    ("arts. 186 do CC", "art_186_ccb"),
    ("arts. 186 e 927 do CC", None),
    ("Lei 13.467/2017 foo", None),
])
def test_codigo_de_texto(texto, esperado):
    assert codigo_de_texto(texto) == esperado

def test_codigo_de_texto_e_rotulo_sao_inversos():
    for c in ["art_15_clt", "b_ii_art_10_adct", "prgf_2_art_791_clt", "sumula_85_tst", "oj_394_sdi1_tst",
              "lv_art_5_cf", "lei_13467_17"]:
        assert codigo_de_texto(rotulo(c)) == c

@pytest.mark.parametrize("texto,esperado", [
    ("clt 15", ["clt", "15"]),
    ("Art. 15 CLT", ["art", "15", "clt"]),
    ("§ 2º art 791", ["prgf", "2", "art", "791"]),
    ("Súmula 85", ["sumula", "85"]),
    ("lei 8.078/90", ["lei", "8078", "90"]),
    ("CC 186", ["ccb", "186"]),
    ("Súmula 85 do TST", ["sumula", "85", "tst"]),
    ("art 10 do adct", ["art", "10", "adct"]),
    ("Súmula nº 85", ["sumula", "85"]),
    ("CF/88 art 5", ["cf", "art", "5"]),
    ("SBDI-1", ["sdi1"]),
    ("arts. 186", ["art", "186"]),
])
def test_tokens_da_busca(texto, esperado):
    assert tokens_da_busca(texto) == esperado


@pytest.mark.parametrize("norma,texto,esperado", [
    ("CLT art. 192", "Pede o adicional com base no art. 192 da CLT.", True),
    ("NR-15", "conforme a NR 15, anexo 1", True),
    ("Súmula 85 do TST", "aplica-se a súmula nº 85 do TST", True),
    ("ADCT art. 10, II, b", "A gestante dispensada tem estabilidade.", False),
    ("CLT art. 193", "O bancário em cargo de confiança quer a 7ª e 8ª horas.", False),
    ("CLT art. 192", "art. 192 do código", False),  # número sem a lei
])
def test_citada_em(norma, texto, esperado):
    from query.filtros.dispositivos import citada_em
    assert citada_em(norma, texto) is esperado


@pytest.mark.parametrize("texto,esperado", [
    ("nos termos da NR-15, anexo 1", {"nr_15"}),
    ("conforme NR 16 e a Norma Regulamentadora nº 17", {"nr_16", "nr_17"}),
    ("NR 06 do MTE", {"nr_6"}),
    ("Tema 1046 da repercussão geral", {"tema_1046"}),
    ("tema nº 725 do STF", {"tema_725"}),
    ("o tema central do recurso", set()),
    ("Súmula Vinculante 4", {"sv_4"}), ("Súmula Vinculante nº 40", {"sv_40"}), ("SV 13", {"sv_13"}),
    ("Súmula 4 do STF e Súmula 85 do TST", set()),
    ("CNR 15 e NRA-2", set()),  # NR dentro de outra sigla
    ("Nr 0001639-12.2023.5.04.0001", set()), ("NR 0", set()), ("NR 95", set()), ("NR-38", {"nr_38"}),
    ("Temas 1046 e 725", {"tema_1046", "tema_725"}),
    ("Temas 1046, 725 e 1232", {"tema_1046", "tema_725", "tema_1232"}),
    ("NRs 15 e 16", {"nr_15", "nr_16"}),
    ("Súmulas Vinculantes 4 e 13", {"sv_4", "sv_13"}),
    ("tema e NR 15", {"nr_15"}),
    ("Tema 1046 e 2 testemunhas", {"tema_1046"}), ("Tema nº 725 e 1 hora", {"tema_725"}),
    ("Súmula vinculante 4, 2 partes", {"sv_4"}), ("NR 15, 3 anos", {"nr_15"}), ("NR 15 e 16 horas", {"nr_15"}),
])
def test_codigos_do_texto(texto, esperado):
    assert codigos_do_texto(texto) == esperado


def test_rotulo_dos_codigos_novos():
    assert rotulo("nr_15") == "NR-15" and rotulo("tema_1046") == "Tema 1046" and rotulo("sv_4") == "Súmula Vinculante 4"


def test_conversao_e_busca_dos_codigos_novos():
    assert codigo_de_texto("NR-15") == "nr_15" and codigo_de_texto("Tema 1046") == "tema_1046" and codigo_de_texto("Súmula Vinculante 4") == "sv_4"
    assert codigo_de_texto("Súmula 4 do STF") != "sv_4"
    assert tokens_da_busca("nr 15") == ["nr", "15"]
    assert tokens_da_busca("súmula vinculante 4") == ["sv", "4"] and tokens_da_busca("vinculante 4") == ["sv", "4"]
    assert niveis("nr_15") == ["nr_15"] and eh_dispositivo("tema_1046")
