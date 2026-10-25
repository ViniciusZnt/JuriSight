import { groupByRecency, type Conversation } from "@/lib/conversations";

// Meio-dia de N dias atrás, evitando flakiness perto da virada da meia-noite.
function daysAgo(n: number): number {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() - n);
  return d.getTime();
}

function conv(id: string, createdAt: number): Conversation {
  return { id, title: `Consulta ${id}`, createdAt };
}

describe("groupByRecency", () => {
  it("agrupa uma conversa de hoje no bucket 'Hoje'", () => {
    const groups = groupByRecency([conv("1", daysAgo(0))]);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Hoje");
    expect(groups[0].items.map((c) => c.id)).toEqual(["1"]);
  });

  it("agrupa uma conversa de ontem no bucket 'Ontem'", () => {
    const groups = groupByRecency([conv("1", daysAgo(1))]);
    expect(groups.map((g) => g.label)).toEqual(["Ontem"]);
  });

  it("agrupa uma conversa de 3 dias atrás em 'Esta semana'", () => {
    const groups = groupByRecency([conv("1", daysAgo(3))]);
    expect(groups.map((g) => g.label)).toEqual(["Esta semana"]);
  });

  it("agrupa uma conversa de 10 dias atrás em 'Mais antigas'", () => {
    const groups = groupByRecency([conv("1", daysAgo(10))]);
    expect(groups.map((g) => g.label)).toEqual(["Mais antigas"]);
  });

  it("só inclui buckets com pelo menos uma conversa, na ordem Hoje → Ontem → Esta semana → Mais antigas", () => {
    const groups = groupByRecency([
      conv("antiga", daysAgo(30)),
      conv("hoje", daysAgo(0)),
      conv("semana", daysAgo(4)),
    ]);
    expect(groups.map((g) => g.label)).toEqual(["Hoje", "Esta semana", "Mais antigas"]);
  });

  it("ordena as conversas dentro de cada bucket da mais recente para a mais antiga", () => {
    const groups = groupByRecency([
      conv("cedo", daysAgo(0) - 5000),
      conv("tarde", daysAgo(0)),
    ]);
    expect(groups[0].items.map((c) => c.id)).toEqual(["tarde", "cedo"]);
  });

  it("retorna lista vazia quando não há conversas", () => {
    expect(groupByRecency([])).toEqual([]);
  });
});
