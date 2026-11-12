import { assuntoDoCard, orgaoDe, orgaosCitados, vereditoDe, dispositivoDe, dispositivoETexto, itensDaFrase, ementaComCitacao, ementasRepetidas, paragrafos, relevanceRanks, respostaParaCopiar, titleFromEmenta, tituloDoCard } from "@/lib/decision-view";

describe("relevanceRanks", () => {
  it("numera do mais ao menos relevante, sem depender da ordem de entrada", () => {
    const ranks = relevanceRanks([
      { id: "b", score_rrf: 0.4 },
      { id: "a", score_rrf: 1 },
      { id: "c", score_rrf: 0 },
    ]);
    expect([ranks.get("a"), ranks.get("b"), ranks.get("c")]).toEqual([1, 2, 3]);
  });

  it("empates não repetem a posição: mantém a ordem em que a API devolveu", () => {
    const ranks = relevanceRanks([
      { id: "x", score_rrf: 1 },
      { id: "y", score_rrf: 1 },
    ]);
    expect([ranks.get("x"), ranks.get("y")]).toEqual([1, 2]);
  });
});

describe("titleFromEmenta", () => {
  it("usa a verbetação sem os genéricos, para os títulos não repetirem", () => {
    expect(
      titleFromEmenta("Ementa: DIREITO DO TRABALHO. RECURSO ORDINÁRIO. ADICIONAL DE INSALUBRIDADE. RUÍDO. EPIS INEFICAZES. I. CASO EM EXAME 1. Recurso da reclamada.")
    ).toBe("ADICIONAL DE INSALUBRIDADE. RUÍDO. EPIS INEFICAZES.");
    expect(titleFromEmenta("RECURSO DA RECLAMADA - ADICIONAL DE INSALUBRIDADE - FRIO. Mantida a sentença.")).toBe(
      "RECURSO DA RECLAMADA. ADICIONAL DE INSALUBRIDADE. FRIO."
    );
  });

  it("sem verbetação, cai na primeira frase", () => {
    expect(titleFromEmenta("Comprovada a exposição ao ruído, é devido o adicional. Recurso provido.")).toBe(
      "Comprovada a exposição ao ruído, é devido o adicional."
    );
    expect(titleFromEmenta("  ")).toBe("Decisão sem ementa disponível");
  });
});

describe("ementasRepetidas", () => {
  it("marca a ementa praticamente igual à de um resultado mais bem posicionado", () => {
    const base = "ADICIONAL DE INSALUBRIDADE. EXPOSIÇÃO AO FRIO E RUÍDO. INSUFICIÊNCIA DOS EPIS. MANUTENÇÃO DA CONDENAÇÃO. " +
      "Comprovada pela perícia a exposição a frio e ruído sem neutralização pelos equipamentos fornecidos, mantém-se o adicional em grau médio.";
    const r = ementasRepetidas([
      { id: "a", ementa: base },
      { id: "b", ementa: "HORAS EXTRAS. Motorista com jornada controlada." },
      { id: "c", ementa: base.replace("grau médio", "grau  médio.") },
    ]);
    expect([...r]).toEqual([["c", "a"]]);
  });
});

describe("ementaComCitacao", () => {
  it("junta a ementa e a linha de citação", () => {
    expect(
      ementaComCitacao({ ementa: " Texto. ", tribunal: "TRT2", turma: "11ª Turma", numero_processo: "0001", data_julgamento: "2025-12-17", relator: "Fulana" })
    ).toBe("Texto.\n\n(TRT2, 11ª Turma, Processo 0001, julgado em 17/12/2025, Rel. Fulana.)");
  });
});

describe("tituloDoCard", () => {
  it("põe classe e identificação antes da verbetação; sem classe (cards antigos), só tribunal e turma", () => {
    const d = { ementa: "ADICIONAL DE INSALUBRIDADE. RUÍDO. Texto da ementa.", tribunal: "TRT2", turma: "11ª Turma", data_julgamento: null };
    expect(tituloDoCard({ ...d, sigla_classe: "RORSum", data_julgamento: "2025-05-12" })).toBe(
      "RORSum · TRT2 · 11ª Turma · 12/05/2025 — ADICIONAL DE INSALUBRIDADE. RUÍDO."
    );
    expect(tituloDoCard(d)).toBe("TRT2 · 11ª Turma — ADICIONAL DE INSALUBRIDADE. RUÍDO.");
  });
});

describe("respostaParaCopiar", () => {
  it("marca as citações em cada frase e lista só as decisões citadas, em ordem", () => {
    const dec = (p: string) => ({ tribunal: "TRT2", turma: "11ª Turma", numero_processo: p, data_julgamento: "2025-05-12", relator: "" });
    const porNumero = new Map([[1, dec("0001")], [2, dec("0002")], [3, dec("0003")]]);
    const frases = [
      { texto: "Sim, com perícia.", citacoes: [3, 1] },
      { texto: "CLT, art. 189.", citacoes: [] },
      { texto: "Negaram por EPI eficaz.", citacoes: [3] },
    ];
    expect(respostaParaCopiar(frases, porNumero)).toBe(
      "Sim, com perícia. [3, 1] CLT, art. 189. Negaram por EPI eficaz. [3]\n\nDecisões citadas:\n" +
        "[1] TRT2, 11ª Turma, Processo 0001, julgado em 12/05/2025.\n[3] TRT2, 11ª Turma, Processo 0003, julgado em 12/05/2025."
    );
  });
});

describe("paragrafos", () => {
  it("respeita as quebras do original e, sem elas, quebra antes de itens numerados", () => {
    expect(paragrafos("Um.\n\nDois.")).toEqual(["Um.", "Dois."]);
    expect(paragrafos("CASO. I. CASO EM EXAME 1. Recurso da ré, art. 895, I, da CLT. II. QUESTÃO em discussão")).toEqual([
      "CASO.",
      "I. CASO EM EXAME",
      "1. Recurso da ré, art. 895, I, da CLT.",
      "II. QUESTÃO em discussão",
    ]);
  });
});

describe("dispositivoDe", () => {
  it("pega do último ACORDAM em diante; sem ele, do último 'exposto'", () => {
    expect(dispositivoDe("Fundamentos. Ante o exposto, nego. ACORDAM os Magistrados em negar provimento.")).toBe(
      "ACORDAM os Magistrados em negar provimento."
    );
    expect(dispositivoDe("Ante o exposto, A. Diante do exposto, dou provimento.")).toBe("Diante do exposto, dou provimento.");
    expect(dispositivoDe("Sem dispositivo reconhecível.")).toBeNull();
  });

  it("corta textos longos numa frase", () => {
    expect(dispositivoDe("ACORDAM em dar provimento. Participaram os desembargadores fulano e beltrano.", 40)).toBe(
      "ACORDAM em dar provimento. […]"
    );
  });
});

describe("itensDaFrase", () => {
  it("separa por ; com maiúscula e sem ponto final", () => {
    expect(itensDaFrase("CLT art. 189: se insalubre, adicional; Súmula 80 do TST: se o EPI elimina, não.")).toEqual([
      "CLT art. 189: se insalubre, adicional",
      "Súmula 80 do TST: se o EPI elimina, não",
    ]);
  });

  it("sem o prefixo até os dois-pontos", () => {
    expect(itensDaFrase("Para o pedido, é preciso provar: a gravidez; a dispensa sem justa causa.", true)).toEqual([
      "A gravidez",
      "A dispensa sem justa causa",
    ]);
  });
});

describe("dispositivoETexto", () => {
  it("separa o dispositivo do que ele diz", () => {
    expect(dispositivoETexto("CLT art. 10, II, 'b': se a empregada está grávida, é vedada a dispensa")).toEqual([
      "CLT art. 10, II, 'b'",
      "Se a empregada está grávida, é vedada a dispensa",
    ]);
    expect(dispositivoETexto("NR-15 Anexo 1")).toEqual([null, "NR-15 Anexo 1"]);
  });
});


describe("assuntoDoCard", () => {
  it("passa o assunto em maiúsculas para frase, mantendo as siglas", () => {
    expect(assuntoDoCard("MOTORISTA PROFISSIONAL. HORAS EXTRAS. ART. 62, I, DA CLT.")).toBe("Motorista profissional. Horas extras. Art. 62, I, da CLT.");
    expect(assuntoDoCard("ADICIONAL DE INSALUBRIDADE. EPI INEFICAZ. NR-15.")).toBe("Adicional de insalubridade. EPI ineficaz. NR-15.");
    expect(assuntoDoCard("SÚMULA 338 DO TST. CONTROLE DE JORNADA.")).toBe("Súmula 338 do TST. Controle de jornada.");
  });

  it("não mexe em assunto que já tem minúsculas", () => {
    expect(assuntoDoCard("Comprovada a exposição ao ruído, é devido o adicional.")).toBe("Comprovada a exposição ao ruído, é devido o adicional.");
  });
});


describe("orgaoDe", () => {
  it("escreve o órgão no padrão de citação, com o tribunal hifenizado", () => {
    expect(orgaoDe({ tribunal: "TRT4", turma: "1ª Turma" })).toBe("1ª Turma do TRT-4");
    expect(orgaoDe({ tribunal: "TRT6", turma: "Quarta Turma" })).toBe("4ª Turma do TRT-6");
    expect(orgaoDe({ tribunal: "TRT2", turma: "03ª Turma" })).toBe("3ª Turma do TRT-2");
    expect(orgaoDe({ tribunal: "TRT9", turma: "3ª TURMA" })).toBe("3ª Turma do TRT-9");
    expect(orgaoDe({ tribunal: "TRT15", turma: "11ª Câmara" })).toBe("11ª Câmara do TRT-15");
    expect(orgaoDe({ tribunal: "TRT3", turma: "Décima Primeira Turma" })).toBe("11ª Turma do TRT-3");
    expect(orgaoDe({ tribunal: "TST", turma: "" })).toBe("TST");
  });

  it("orgaosCitados junta órgãos repetidos e mostra no máximo dois", () => {
    const d = (tribunal: string, turma: string) => ({ tribunal, turma });
    expect(orgaosCitados([d("TRT4", "1ª Turma"), d("TRT4", "1ª Turma")])).toBe("1ª Turma do TRT-4");
    expect(orgaosCitados([d("TRT4", "1ª Turma"), d("TRT22", "2ª Turma")])).toBe("1ª Turma do TRT-4 e 2ª Turma do TRT-22");
    expect(orgaosCitados([d("TRT4", "1ª Turma"), d("TRT22", "2ª Turma"), d("TRT9", "3ª Turma")])).toBe("1ª Turma do TRT-4, 2ª Turma do TRT-22 e mais 1");
  });
});

describe("vereditoDe", () => {
  it("separa o Sim/Não/Depende do começo da resposta", () => {
    expect(vereditoDe("Sim. Há horas extras a pagar.")).toEqual({ veredito: "Sim", resto: "Há horas extras a pagar." });
    expect(vereditoDe("Sim, quando a ausência de controle gera presunção.")).toEqual({ veredito: "Sim", resto: "Quando a ausência de controle gera presunção." });
    expect(vereditoDe("Não, porque o EPI era eficaz.")).toEqual({ veredito: "Não", resto: "Porque o EPI era eficaz." });
    expect(vereditoDe("Depende de prova da exposição.")).toEqual({ veredito: "Depende", resto: "de prova da exposição." });
    expect(vereditoDe("Há divergência entre as turmas.")).toEqual({ veredito: null, resto: "Há divergência entre as turmas." });
  });
});
