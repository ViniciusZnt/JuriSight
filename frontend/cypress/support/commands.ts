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

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      /** Faz login mockado (qualquer credencial preenchida entra) e reaproveita a sessão entre testes. */
      login(email?: string, password?: string): Chainable<void>;
    }
  }
}

export {};
