import { OUTCOME_CONFIG, provimentoToOutcome, type Outcome } from "@/lib/outcome";
import type { Provimento } from "@/lib/api";

describe("OUTCOME_CONFIG", () => {
  const outcomes: Outcome[] = ["favorable", "unfavorable", "neutral"];

  it("tem uma entrada para cada provimento possível", () => {
    for (const outcome of outcomes) {
      expect(OUTCOME_CONFIG[outcome]).toBeDefined();
    }
  });

  it("cada entrada tem rótulo, ícone e classes de estilo", () => {
    for (const outcome of outcomes) {
      const config = OUTCOME_CONFIG[outcome];
      expect(typeof config.label).toBe("string");
      expect(config.label.length).toBeGreaterThan(0);
      expect(config.icon).toBeDefined();
      expect(config.bg).toMatch(/bg-/);
      expect(config.text).toMatch(/text-/);
    }
  });

  it("usa rótulos em português alinhados ao provimento", () => {
    expect(OUTCOME_CONFIG.favorable.label).toBe("Favorável");
    expect(OUTCOME_CONFIG.unfavorable.label).toBe("Desfavorável");
    expect(OUTCOME_CONFIG.neutral.label).toBe("Neutro");
  });
});

describe("provimentoToOutcome", () => {
  it("mapeia APROVADO para favorable", () => {
    expect(provimentoToOutcome("APROVADO")).toBe("favorable");
  });

  it("mapeia NEGADO para unfavorable", () => {
    expect(provimentoToOutcome("NEGADO")).toBe("unfavorable");
  });

  it("mapeia PARCIAL e NAO_APLICAVEL para neutral", () => {
    expect(provimentoToOutcome("PARCIAL")).toBe("neutral");
    expect(provimentoToOutcome("NAO_APLICAVEL")).toBe("neutral");
  });

  it("cobre todos os valores de Provimento sem lançar", () => {
    const todos: Provimento[] = ["APROVADO", "PARCIAL", "NEGADO", "NAO_APLICAVEL"];
    for (const p of todos) {
      expect(() => provimentoToOutcome(p)).not.toThrow();
    }
  });
});
