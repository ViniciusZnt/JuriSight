describe("Fluxo principal de consulta (UC01/UC02)", () => {
  beforeEach(() => {
    cy.login();
  });

  it("com PDF anexado, segue para a revisão com o passo 'Documento enviado'", () => {
    cy.visit("/");
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 conteudo de teste"), fileName: "peticao.pdf" },
      { force: true }
    );
    cy.get("textarea").click();
    cy.get("textarea").type("{enter}");
    cy.url().should("include", "/revisao");
    cy.url().should("not.include", "modo=manual");
    cy.contains("Documento enviado");
  });

  it("sem PDF, segue para a revisão manual (UC02 / FA01) com campos vazios", () => {
    cy.visit("/");
    cy.get("textarea").type("Quero provar insalubridade por benzeno sem EPI{enter}");
    cy.url().should("include", "/revisao?modo=manual");
    cy.contains("Consulta iniciada");
    cy.contains("Busca sem contexto de documento");
    cy.contains("Complete o contexto jurídico");
  });

  it("da revisão, 'Buscar jurisprudências' leva aos resultados", () => {
    cy.visit("/revisao");
    cy.contains("button", "Buscar jurisprudências").click();
    cy.url().should("include", "/resultados");
    cy.contains("decisões encontradas");
  });

  it("'Refinar consulta' nos resultados volta para a revisão", () => {
    cy.visit("/resultados");
    cy.contains("Refinar consulta").click();
    cy.url().should("include", "/revisao");
  });

  it("salvar um resultado faz ele aparecer em Salvos, e continua salvo no detalhe", () => {
    cy.visit("/resultados");
    cy.contains("h3", "Adicional de insalubridade")
      .closest(".group")
      .within(() => cy.contains("button", "Salvar").click());

    cy.visit("/salvos");
    cy.contains("Adicional de insalubridade");

    cy.visit("/decisao/1");
    cy.contains("button", "Salvo").should("exist");
  });
});
