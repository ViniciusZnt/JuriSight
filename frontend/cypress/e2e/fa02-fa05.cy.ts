// FA04 (documento extenso) virou transparente dentro do próprio POST /enrich (sumarização
// hierárquica no backend) — não há mais um sinal client-side distinto pra testar aqui, por isso
// este spec cobre só a FA02 (PDF sem texto extraível) e o caminho de erro de rede/API.
describe("FA02 (PDF sem texto extraível) e erros de API", () => {
  beforeEach(() => {
    cy.login();
    cy.visit("/");
  });

  it("FA02 — mostra o alerta dentro do chat com o aviso real do backend", () => {
    cy.mockEnrichFa02();
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 fake scan"), fileName: "peticao_scan.pdf" },
      { force: true }
    );
    cy.get("textarea").type("{enter}");
    cy.wait("@enrich");

    cy.contains(/Não foi possível extrair texto de/);
    cy.contains("peticao_scan.pdf");
    cy.contains("Não foi possível extrair texto do PDF");
    cy.url().should("eq", Cypress.config().baseUrl + "/"); // não navegou

    cy.contains("button", "Reenviar arquivo").click();
    cy.contains(/Não foi possível extrair texto de/).should("not.exist");
  });

  it("FA02 — 'Continuar sem o PDF' usa a EstruturaArgumentativa já extraída, sem rechamar /enrich", () => {
    cy.mockEnrichFa02();
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from("%PDF-1.4 fake scan"), fileName: "peticao_scan.pdf" },
      { force: true }
    );
    cy.get("textarea").type("{enter}");
    cy.wait("@enrich");
    cy.get("@enrich.all").should("have.length", 1);

    cy.contains("button", "Continuar sem o PDF").click();
    cy.url().should("include", "/revisao?modo=manual");
    cy.get("@enrich.all").should("have.length", 1); // ainda 1 — não rechamou a API
    cy.contains("adicional de insalubridade grau máximo");
  });

  it("erro de rede em /enrich mostra um banner com opção de tentar novamente", () => {
    cy.intercept("POST", "**/enrich", { forceNetworkError: true }).as("enrichFalha");
    cy.get("textarea").type("adicional de insalubridade{enter}");
    cy.wait("@enrichFalha");
    cy.contains("Não foi possível conectar ao servidor");

    cy.mockEnrichSucesso();
    cy.contains("button", "Tentar novamente").click();
    cy.wait("@enrich");
    cy.url().should("include", "/revisao");
  });
});
