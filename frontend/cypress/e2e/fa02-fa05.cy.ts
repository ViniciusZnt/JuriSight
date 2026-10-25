describe("FA02 (PDF sem texto extraível) e FA05 (documento extenso)", () => {
  beforeEach(() => {
    cy.login();
    cy.visit("/");
  });

  it("FA02 — mostra o alerta dentro do chat e permite reenviar o arquivo", () => {
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 fake scan"), fileName: "peticao_scan.pdf" },
      { force: true }
    );
    cy.get("textarea").type("{enter}");

    cy.contains(/Não foi possível extrair texto de/);
    cy.contains("peticao_scan.pdf");
    cy.contains("Não foi possível extrair texto do PDF enviado (possível documento escaneado)");
    cy.url().should("eq", Cypress.config().baseUrl + "/"); // não navegou

    cy.contains("button", "Reenviar arquivo").click();
    cy.contains(/Não foi possível extrair texto de/).should("not.exist");
  });

  it("FA02 — 'Continuar sem o PDF' segue para a revisão manual", () => {
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 fake scan"), fileName: "peticao_scan.pdf" },
      { force: true }
    );
    cy.get("textarea").type("{enter}");
    cy.contains("button", "Continuar sem o PDF").click();
    cy.url().should("include", "/revisao?modo=manual");
  });

  it("FA05 — documento extenso mostra o processamento em blocos antes de seguir", () => {
    const bigFile = Cypress.Buffer.alloc(9 * 1024 * 1024, "a"); // > 8MB, aciona a FA05
    cy.get('input[type="file"]').selectFile(
      { contents: bigFile, fileName: "peticao_grande.pdf" },
      { force: true }
    );
    cy.get("textarea").type("{enter}");

    cy.contains("Documento extenso detectado");
    cy.contains("Processando");
    cy.url().should("include", "/revisao", { timeout: 5000 });
  });
});
