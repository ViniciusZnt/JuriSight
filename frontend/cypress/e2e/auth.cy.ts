describe("Autenticação e proteção de rotas", () => {
  beforeEach(() => {
    Cypress.session.clearAllSavedSessions();
  });

  it("redireciona para /login quem tenta abrir o app sem sessão", () => {
    cy.visit("/");
    cy.url().should("include", "/login");
  });

  it("redireciona para /login quem tenta abrir uma tela interna sem sessão", () => {
    cy.visit("/resultados");
    cy.url().should("include", "/login");
  });

  it("faz login com qualquer credencial preenchida e entra no app", () => {
    cy.visit("/login");
    cy.get('input[type="email"]').type("ana@escritorio.com.br");
    cy.get('input[type="password"]').type("senha123");
    cy.get('button[type="submit"]').click();
    cy.url().should("eq", Cypress.config().baseUrl + "/");
    cy.contains("Pesquisa contextual de");
  });

  it("redireciona para / quem já está logado e tenta abrir /login", () => {
    cy.login();
    cy.visit("/login");
    cy.url().should("eq", Cypress.config().baseUrl + "/");
  });

  it("cadastra uma conta nova e entra direto", () => {
    Cypress.session.clearAllSavedSessions();
    cy.visit("/registro");
    cy.get('input[placeholder="Seu nome"]').type("Ana Paula Rebello");
    cy.get('input[type="email"]').type("ana.rebello@escritorio.com.br");
    cy.get('input[type="password"]').first().type("senha123");
    cy.get('input[type="password"]').eq(1).type("senha123");
    cy.contains("button", "Criar conta").click();
    cy.url().should("eq", Cypress.config().baseUrl + "/");
  });

  it("bloqueia o cadastro quando as senhas não coincidem", () => {
    cy.visit("/registro");
    cy.get('input[type="password"]').first().type("abcdef");
    cy.get('input[type="password"]').eq(1).type("xyzxyz");
    cy.contains("As senhas não coincidem");
    cy.contains("button", "Criar conta").should("be.disabled");
  });

  it("sai da conta pelo botão da sidebar e volta a exigir login", () => {
    cy.login();
    cy.visit("/");
    cy.get('button[title="Sair"]').click();
    cy.url().should("include", "/login");
    cy.visit("/");
    cy.url().should("include", "/login");
  });
});
