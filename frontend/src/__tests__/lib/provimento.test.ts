import type { ClassificacaoProvimento } from "@/lib/api";
import { nivelConfianca, outcomeDe, probabilidadesOrdenadas, resumoProvimento } from "@/lib/provimento";

const base: ClassificacaoProvimento = {
  resultado: "nao_provido",
  recorrente: "reclamada",
  favorece: "reclamante",
  probabilidades: {},
  confianca_resultado: 0.9,
  confianca_recorrente: 0.9,
  confianca_favorece: 0.6,
  modelo: "jev-1.13.0",
};

describe("nivelConfianca", () => {
  it("usa os cortes 0,8 e 0,5", () => {
    expect(nivelConfianca(0.8)).toBe("alta");
    expect(nivelConfianca(0.79)).toBe("media");
    expect(nivelConfianca(0.5)).toBe("media");
    expect(nivelConfianca(0.49)).toBe("baixa");
    expect(nivelConfianca(null)).toBe("baixa");
  });
});

describe("probabilidadesOrdenadas", () => {
  it("ordena da maior para a menor", () => {
    expect(probabilidadesOrdenadas({ a: 0.1, b: 0.7 })[0].valor).toBe("b");
    expect(probabilidadesOrdenadas(undefined)).toEqual([]);
  });
});

describe("outcomeDe", () => {
  it("usa a quem favorece com confiança >= 0,5", () => {
    expect(outcomeDe({ provimento: "APROVADO", classificacao_provimento: base })).toBe("favorable");
    expect(outcomeDe({ provimento: "NEGADO", classificacao_provimento: { ...base, favorece: "reclamada", confianca_favorece: 0.9 } })).toBe("unfavorable");
    expect(outcomeDe({ provimento: "NEGADO", classificacao_provimento: { ...base, confianca_favorece: 0.4 } })).toBe("neutral");
    expect(outcomeDe({ provimento: "NEGADO", classificacao_provimento: { ...base, favorece: "ambos_em_parte", confianca_favorece: 0.9 } })).toBe("neutral");
  });

  it("sem classificação cai na heurística antiga", () => {
    expect(outcomeDe({ provimento: "NEGADO" })).toBe("favorable");
    expect(outcomeDe({ provimento: "APROVADO", classificacao_provimento: null })).toBe("unfavorable");
  });
});

describe("resumoProvimento", () => {
  it("monta recorrente, resultado e a quem favorece", () => {
    expect(resumoProvimento(base)).toBe("Recurso da reclamada (empresa) · Não provido · Favorece: Trabalhador");
  });
});
