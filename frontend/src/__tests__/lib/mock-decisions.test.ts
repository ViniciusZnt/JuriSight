import { mockResults, findDecision } from "@/lib/mock-decisions";

describe("mockResults", () => {
  it("tem ids únicos", () => {
    const ids = mockResults.map((d) => d.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("todo resultado tem número de processo, relator e link implícito pela fonte (RF06 — fonte real)", () => {
    for (const d of mockResults) {
      expect(d.processNumber.length).toBeGreaterThan(0);
      expect(d.rapporteur.length).toBeGreaterThan(0);
      expect(d.court.length).toBeGreaterThan(0);
    }
  });
});

describe("findDecision", () => {
  it("encontra a decisão pelo id", () => {
    const found = findDecision("2");
    expect(found.id).toBe("2");
  });

  it("cai para o primeiro resultado quando o id não existe", () => {
    const found = findDecision("id-que-nao-existe");
    expect(found).toEqual(mockResults[0]);
  });
});
