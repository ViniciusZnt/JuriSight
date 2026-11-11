import pytest
from query.filtros.dispositivos import niveis, eh_dispositivo, rotulo, codigo_de_texto, tokens_da_busca

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
    ("NR-15", None),
    ("Súmula 85, item VI, do TST", "vi_sumula_85_tst"),
    ("CLT art. 192 e art. 193", None),
    ("art. 5 7 CLT", None),
    ("Súmula 85 do TST foo", None),
    ("", None),
])
def test_codigo_de_texto(texto, esperado):
    assert codigo_de_texto(texto) == esperado

def test_codigo_de_texto_e_rotulo_sao_inversos():
    for c in ["art_15_clt", "b_ii_art_10_adct", "prgf_2_art_791_clt", "sumula_85_tst", "oj_394_sdi1_tst"]:
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
])
def test_tokens_da_busca(texto, esperado):
    assert tokens_da_busca(texto) == esperado
