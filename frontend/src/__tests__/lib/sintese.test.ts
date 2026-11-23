import type { ClassificacaoProvimento } from "@/lib/api";
import { citacoesDe, sintetizar } from "@/lib/sintese";

const cls = (favorece: ClassificacaoProvimento["favorece"], confianca_favorece = 0.9): ClassificacaoProvimento => ({
  resultado: "nao_provido",
  recorrente: "reclamada",
  favorece,
  probabilidades: {},
  confianca_resultado: 0.9,
  confianca_recorrente: 0.9,
  confianca_favorece,
  modelo: "jev",
});

const doc = (id: string, score: number, c: ClassificacaoProvimento | null, ementa = "") => ({
  id,
  score_rrf: score,
  ementa,
  provimento: "NAO_APLICAVEL" as const,
  classificacao_provimento: c,
});

describe("citacoesDe", () => {
  it("normaliza súmulas, OJs, artigos da CLT, NR, Tema e ARE/RE", () => {
    const texto =
      "SÚMULA Nº 289 DO C. TST. Súmula 448, I, do TST. OJ 118 da SDI-I TST. Orientação Jurisprudencial nº 173 da SBDI-1. " +
      "Arts. 189 e 191 da CLT; art. 895, § 1º, IV, da CLT. NR 15, Anexo 1. Norma Regulamentadora nº 6. " +
      "STF, ARE 664335/SC (Tema 555). TEMA REPETITIVO Nº 0005.";
    expect(citacoesDe(texto).sort()).toEqual(
      [
        "Súmula 289 do TST",
        "Súmula 448 do TST",
        "OJ 118 da SDI-1",
        "OJ 173 da SDI-1",
        "art. 189 da CLT",
        "art. 191 da CLT",
        "art. 895 da CLT",
        "NR-15",
        "NR-6",
        "ARE 664.335",
        "Tema 555",
        "Tema 5",
      ].sort()
    );
  });

  it("não conta a mesma citação duas vezes no mesmo texto", () => {
    expect(citacoesDe("NR-15 ... NR 15 ... Norma Regulamentadora 15")).toEqual(["NR-15"]);
  });

  it("aceita qualificadores encadeados sem vírgula antes de 'da CLT'", () => {
    expect(citacoesDe("art. 5, parágrafo único inciso II da CLT")).toEqual(["art. 5 da CLT"]);
    expect(citacoesDe("art. 9, I II III IV V VI da CLT")).toEqual(["art. 9 da CLT"]);
    expect(citacoesDe("art. 896, § 1º-A, inciso I alínea a da CLT")).toEqual(["art. 896 da CLT"]);
    expect(citacoesDe("art. 7º, XXIX, da CF/88 e da CLT")).toEqual([]);
  });

  it("não trava em texto longo sem citação completa (sem backtracking super-linear)", () => {
    const inicio = Date.now();
    citacoesDe(`Súmula 1${" ".repeat(50_000)}x NR${" ".repeat(50_000)}x OJ 1${" ".repeat(50_000)}x art. 1, ${"I ".repeat(5_000)}x`);
    expect(Date.now() - inicio).toBeLessThan(500);
  });
});

describe("sintetizar", () => {
  it("sem resultados não há síntese", () => {
    expect(sintetizar([])).toBeNull();
  });

  it("conta pelo mesmo critério do selo (confiança baixa = sem lado) e só diz maioria quando é clara", () => {
    const s = sintetizar([
      doc("a", 0.9, cls("reclamante")),
      doc("b", 0.8, cls("reclamante")),
      doc("c", 0.7, cls("reclamante")),
      doc("d", 0.6, cls("reclamada", 0.3)), // confiança baixa → sem lado
      doc("e", 0.5, cls("reclamada")),
    ])!;
    expect(s.tendencia).toBe("Das 5 decisões, 3 favorecem o trabalhador, 1 a empresa e 1 sem lado claro.");
    expect(s.abertura).toBe("A maioria das decisões encontradas favorece o trabalhador.");
    expect(s.trabalhador).toEqual(["a", "b"]);
    expect(s.empresa).toEqual(["e"]);
  });

  it("divisão equilibrada não vira maioria", () => {
    const s = sintetizar([doc("a", 1, cls("reclamante")), doc("b", 0.5, cls("reclamada")), doc("c", 0.2, cls("indefinido"))])!;
    expect(s.abertura).toBe("As decisões se dividem.");
    expect(s.tendencia).toBe("Das 3 decisões, 1 favorece o trabalhador, 1 a empresa e 1 sem lado claro.");
  });

  it("base citada: conta decisões (não ocorrências), ordena pela contagem e guarda os ids", () => {
    const s = sintetizar([
      doc("a", 1, null, "NR-15. Súmula 289 do TST. NR-15 de novo."),
      doc("b", 0.5, null, "NR 15, Anexo 1."),
      doc("c", 0.2, null, "Sem citação."),
    ])!;
    // a Súmula 289, citada só por "a", é ruído e não aparece
    expect(s.base).toEqual([{ rotulo: "NR-15", ids: ["a", "b"] }]);
  });
});
