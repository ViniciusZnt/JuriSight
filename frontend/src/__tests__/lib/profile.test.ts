import { initialsOf, nomeExibido } from "@/lib/profile";

describe("initialsOf", () => {
  it("usa a primeira e a última palavra do nome", () => {
    expect(initialsOf("Marcos Almeida")).toBe("MA");
  });

  it("usa a primeira e a última palavra em nomes com três ou mais partes", () => {
    expect(initialsOf("Ana Paula Rebello")).toBe("AR");
  });

  it("repete as duas primeiras letras quando há só um nome", () => {
    expect(initialsOf("Marcos")).toBe("MA");
  });

  it("ignora espaços extras entre as palavras", () => {
    expect(initialsOf("  Marcos   Almeida  ")).toBe("MA");
  });

  it("retorna '?' para nome vazio", () => {
    expect(initialsOf("")).toBe("?");
    expect(initialsOf("   ")).toBe("?");
  });

  it("sempre retorna maiúsculas", () => {
    expect(initialsOf("marcos almeida")).toBe("MA");
  });
});

describe("nomeExibido", () => {
  it("usa o nome da conta quando existe", () => {
    expect(nomeExibido("Vinicius Zanatta", "vini@exemplo.com")).toBe("Vinicius Zanatta");
  });

  it("sem nome, usa a parte do e-mail antes do @", () => {
    expect(nomeExibido(null, "vini.z@exemplo.com")).toBe("vini.z");
    expect(nomeExibido("   ", "vini.z@exemplo.com")).toBe("vini.z");
  });

  it("sem sessão, fica vazio (nunca um nome de exemplo)", () => {
    expect(nomeExibido(undefined, undefined)).toBe("");
  });
});
