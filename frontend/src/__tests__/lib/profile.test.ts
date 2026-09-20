import { initialsOf } from "@/lib/profile";

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
