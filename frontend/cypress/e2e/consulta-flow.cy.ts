describe("Fluxo principal de consulta (UC01/UC02)", () => {
  beforeEach(() => {
    cy.login();
    cy.mockEnrichSucesso();
    cy.mockQueryResultados();
  });

  it("com PDF anexado, chama /enrich com o arquivo e segue para a revisão", () => {
    cy.visit("/");
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 conteudo de teste"), fileName: "peticao.pdf" },
      { force: true }
    );
    cy.get("textarea").click();
    cy.get("textarea").type("{enter}");
    cy.wait("@enrich").its("request.body").should("contain", "peticao.pdf");
    cy.url().should("include", "/revisao");
    cy.url().should("not.include", "modo=manual");
    cy.contains("Documento enviado");
    // Campos vieram da EstruturaArgumentativa real devolvida por /enrich, não de dados fixos.
    cy.contains("adicional de insalubridade grau máximo");
    cy.contains("benzeno");
  });

  it("sem PDF, segue para a revisão manual (UC02 / FA01)", () => {
    cy.visit("/");
    cy.get("textarea").type("Quero provar insalubridade por benzeno sem EPI{enter}");
    cy.wait("@enrich");
    cy.url().should("include", "/revisao?modo=manual");
    cy.contains("Consulta iniciada");
    cy.contains("Complete o contexto jurídico");
  });

  it("da revisão, 'Buscar jurisprudências' chama /query e leva aos resultados", () => {
    cy.completarConsulta();
    cy.contains("5 decisões encontradas");
  });

  it("'Refinar consulta' nos resultados volta para a revisão", () => {
    cy.completarConsulta();
    cy.contains("Refinar consulta").click();
    cy.url().should("include", "/revisao");
  });

  it("salvar um resultado faz ele aparecer em Salvos, e continua salvo no detalhe", () => {
    cy.mockDocument("acordao-1");
    cy.completarConsulta();

    cy.contains("h3", "TST-RR-100-44.2021.5.01.0019")
      .closest(".group")
      .within(() => cy.contains("button", "Salvar").click());

    cy.visit("/salvos");
    cy.contains("TST-RR-100-44.2021.5.01.0019");

    cy.visit("/decisao/acordao-1");
    cy.wait("@document");
    cy.contains("button", "Salvo").should("exist");
  });
});
