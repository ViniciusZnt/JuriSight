import { conversationTag, groupByRecency, numerarRepetidas, type Conversation, type ConversationVersion } from "@/lib/conversations";

// Meio-dia de N dias atrás, evitando flakiness perto da virada da meia-noite.
function daysAgo(n: number): number {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() - n);
  return d.getTime();
}

function conv(id: string, createdAt: number): Conversation {
  return { id, title: `Consulta ${id}`, createdAt, versions: [] };
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

describe("conversationTag", () => {
  const agora = new Date(2026, 10, 1, 15, 0).getTime();
  const v = { numero: 1 } as ConversationVersion;

  it("mostra a hora para consultas de hoje ou de ontem", () => {
    expect(conversationTag(conv("1", new Date(2026, 10, 1, 9, 5).getTime()), agora)).toBe("09:05");
    expect(conversationTag(conv("1", new Date(2026, 9, 31, 22, 40).getTime()), agora)).toBe("22:40");
  });

  it("mostra dia/mês para consultas mais antigas", () => {
    expect(conversationTag(conv("1", new Date(2026, 9, 20, 9, 5).getTime()), agora)).toBe("20/10");
  });

  it("acrescenta a última versão quando a consulta foi refinada", () => {
    const c = { ...conv("1", new Date(2026, 10, 1, 9, 5).getTime()), versions: [v, v] };
    expect(conversationTag(c, agora)).toBe("09:05 · V2");
  });
});

describe("numerarRepetidas", () => {
  it("numera a partir da 2ª consulta de mesmo título, na ordem em que foram feitas", () => {
    const a = { ...conv("a", 1000), title: "Ruído" };
    const b = { ...conv("b", 1000), title: "Outra" };
    const c = { ...conv("c", 1500), title: "ruído " };
    const d = { ...conv("d", 2000), title: "Ruído" };
    const n = numerarRepetidas([d, c, b, a]);
    expect([n.get("a"), n.get("b"), n.get("c"), n.get("d")]).toEqual([undefined, undefined, 2, 3]);
  });
});
