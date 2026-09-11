import { OUTCOME_CONFIG, type Outcome } from "@/lib/outcome";

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
