describe("Resultados — filtros, ordenação, FA03/FA04 e exportação", () => {
  beforeEach(() => {
    cy.login();
    cy.visit("/resultados");
  });

  it("filtra por provimento favorável/desfavorável", () => {
    cy.contains("button", /^Favoráveis/).click();
    cy.get("h3").should("have.length", 3);

    cy.contains("button", /^Desfavoráveis/).click();
    cy.get("h3").should("have.length", 1);
  });

  it("FA04 — avisa quando o filtro de provimento devolve poucos resultados", () => {
    cy.contains("button", /^Desfavoráveis/).click();
    cy.contains("Apenas 1 resultado encontrado com provimento desfavorável");
    cy.contains("button", "Considere remover o filtro").click();
    cy.get("h3").should("have.length", 5);
  });

  it("filtra por período (data completa, dia/mês/ano)", () => {
    cy.contains("Em qualquer data").click();
    cy.get('input[type="date"]').first().type("2025-04-01");
    cy.get('input[type="date"]').eq(1).type("2025-04-30");
    cy.contains("Aplicar").click();
    cy.get("h3").should("have.length", 2);
  });

  it("FA03 — nenhum documento encontrado, com a mensagem exata do RFC", () => {
    cy.contains("Em qualquer data").click();
    cy.get('input[type="date"]').first().type("2030-01-01");
    cy.get('input[type="date"]').eq(1).type("2030-12-31");
    cy.contains("Aplicar").click();

    cy.contains("Nenhum documento encontrado");
    cy.contains("Nenhum documento encontrado para esta consulta. Tente ampliar a intenção argumentativa ou remover filtros de provimento e período.");
    cy.contains("button", "Remover filtros").click();
    cy.get("h3").should("have.length", 5);
  });

  it("alterna a ordenação entre ascendente e descendente ao clicar na seta", () => {
    cy.get("h3").first().should("contain.text", "Adicional de insalubridade"); // maior relevância primeiro

    cy.get('button[title*="Ordem"]').click();
    cy.get("h3").first().should("contain.text", "Insalubridade — necessidade"); // menor relevância primeiro

    cy.get('button[title*="Ordem"]').click();
    cy.get("h3").first().should("contain.text", "Adicional de insalubridade");
  });

  it("exporta os resultados filtrados como .txt", () => {
    cy.contains("button", "Exportar resultados").click();
    cy.readFile("cypress/downloads/jurisight-resultados.txt").should(
      "contain",
      "5 de 5 resultados"
    );
  });
});
