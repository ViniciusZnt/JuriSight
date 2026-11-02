import { dispositivoDe, ementaComCitacao, ementasRepetidas, paragrafos, relevanceRanks, titleFromEmenta } from "@/lib/decision-view";

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
