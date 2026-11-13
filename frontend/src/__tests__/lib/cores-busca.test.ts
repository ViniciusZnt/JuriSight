import { BUSCA, TOTAL_ACERVO } from "@/lib/cores-busca";

describe("cores das buscas (paleta A)", () => {
  it("cada busca tem nome e cor próprios", () => {
    expect(BUSCA.filtro).toMatchObject({ nome: "Filtro restrito", cor: "#1A3A5C", corSobreMarinho: "#FFFFFF" });
    expect(BUSCA.semantica).toMatchObject({ nome: "Busca semântica", cor: "#6D4FC2", corSobreMarinho: "#B6A5F0" });
    expect(BUSCA.termos).toMatchObject({ nome: "Busca por termos", cor: "#0E8A80", corSobreMarinho: "#5FCFC4" });
  });

  it("total do acervo num lugar só", () => {
    expect(TOTAL_ACERVO).toBe(69349);
  });
});
