/// <reference types="cypress" />

// Sessão mockada (lib/auth.tsx): qualquer e-mail/senha preenchidos entra. cy.session evita
// repetir o login em todo teste — a sessão (localStorage) é restaurada entre specs.
Cypress.Commands.add("login", (email = "ana@escritorio.com.br", password = "senha123") => {
  cy.session(
    [email, password],
    () => {
      cy.visit("/login");
      cy.get('input[type="email"]').type(email);
      cy.get('input[type="password"]').type(password);
      cy.get('button[type="submit"]').click();
      cy.url().should("eq", Cypress.config().baseUrl + "/");
    },
    { cacheAcrossSpecs: true }
  );
});

// Intercepta a API real (query/api/app.py) com fixtures moldadas exatamente como
// EnrichResponse/ResultCard[]/DocumentoDetalhe — os specs testam a integração de verdade
// (parsing da resposta, navegação, estado), não infra real (Postgres/Chroma/Ollama).
Cypress.Commands.add("mockEnrichSucesso", () => {
  cy.intercept("POST", "**/enrich", { fixture: "enrich-sucesso.json" }).as("enrich");
});

Cypress.Commands.add("mockEnrichFa02", () => {
  cy.intercept("POST", "**/enrich", { fixture: "enrich-fa02.json" }).as("enrich");
});

Cypress.Commands.add("mockQueryResultados", () => {
  cy.intercept("POST", "**/query", { fixture: "query-resultados.json" }).as("query");
});

Cypress.Commands.add("mockDocument", (id: string) => {
  cy.fixture("query-resultados.json").then((resultados: { id: string }[]) => {
    const card = resultados.find((r) => r.id === id) ?? resultados[0];
    cy.intercept("GET", `**/document/${id}`, {
      ...card,
      classe_processo: "Recurso de Revista",
      sigla_classe: "RR",
      gabinete: "",
      cabecalho: "",
      relatorio: "",
      fundamentacao: "A controvérsia consiste em definir se há direito ao adicional pleiteado.",
      acordao: "Ante o exposto, nego provimento ao recurso.",
      votos: "",
      referencia_legislativa: ["NR-15", "CLT art. 192"],
    }).as("document");
  });
});

// Percorre Home -> Revisão -> Resultados de ponta a ponta (via a UI de verdade), assumindo que
// mockEnrichSucesso()/mockQueryResultados() já foram chamados. É o único jeito de chegar em
// /resultados com dados desde que a página passou a exigir o contexto da consulta em memória
// (sem isso, ela redireciona pra "/").
Cypress.Commands.add("completarConsulta", (intencao = "adicional de insalubridade por exposição a benzeno") => {
  cy.visit("/");
  cy.get("textarea").type(`${intencao}{enter}`);
  cy.wait("@enrich");
  cy.url().should("include", "/revisao");
  cy.contains("button", "Buscar jurisprudências").click();
  cy.wait("@query");
  cy.url().should("include", "/resultados");
});

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      /** Faz login mockado (qualquer credencial preenchida entra) e reaproveita a sessão entre testes. */
      login(email?: string, password?: string): Chainable<void>;
      /** Intercepta POST /enrich com uma EstruturaArgumentativa extraída com sucesso. */
      mockEnrichSucesso(): Chainable<void>;
      /** Intercepta POST /enrich simulando a FA02 (PDF sem texto extraível). */
      mockEnrichFa02(): Chainable<void>;
      /** Intercepta POST /query com os 5 resultados de cypress/fixtures/query-resultados.json. */
      mockQueryResultados(): Chainable<void>;
      /** Intercepta GET /document/{id} com o card correspondente da fixture de resultados. */
      mockDocument(id: string): Chainable<void>;
      /** Home -> intenção -> Enter -> Revisão -> "Buscar jurisprudências" -> Resultados. */
      completarConsulta(intencao?: string): Chainable<void>;
    }
  }
}

export {};
