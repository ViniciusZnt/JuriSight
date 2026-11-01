import { relevanceRanks } from "@/lib/decision-view";

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
