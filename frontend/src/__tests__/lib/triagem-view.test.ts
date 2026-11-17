import { idsParaResposta, numeracao, organizar, ROTULO_NOTA } from "@/lib/triagem-view";
import type { Avaliacao, ResultCard } from "@/lib/api";

const c = (id: string) => ({ id }) as ResultCard;
const av = (nota: 0 | 1 | 2 | 3): Avaliacao => ({ nota, posicao: "deferiu", motivo: "m" });
const ids = (l: ResultCard[]) => l.map((d) => d.id);

test("rótulos das notas", () => {
  expect(ROTULO_NOTA).toEqual({ 3: "Mesmo problema e fato", 2: "Mesmo pedido", 1: "Mesmo ramo", 0: "Outro tema" });
});

test("relacionadas: nota 3 antes de 2, desempate pela ordem do RRF; depois as votadas na ordem do voto", () => {
  const r = ["a", "b", "c", "d", "e", "f"].map(c);
  const m = new Map([["a", av(2)], ["b", av(3)], ["c", av(2)], ["d", av(3)], ["e", av(0)], ["f", av(1)]]);
  expect(ids(organizar(r, m, ["f", "e"]).relacionadas)).toEqual(["b", "d", "a", "c", "f", "e"]);
});

test("pouco relacionadas: nota 1 antes de 0; votada sai daqui", () => {
  const r = ["a", "b", "c"].map(c);
  const m = new Map([["a", av(0)], ["b", av(1)], ["c", av(0)]]);
  expect(ids(organizar(r, m, ["c"]).poucoRelacionadas)).toEqual(["b", "a"]);
});

test("sem avaliação vai para não avaliadas, na ordem do RRF", () => {
  const r = ["a", "b", "c"].map(c);
  expect(ids(organizar(r, new Map([["b", av(3)]]), []).naoAvaliadas)).toEqual(["a", "c"]);
});

test("numeracao segue relacionadas → não avaliadas → pouco relacionadas", () => {
  const r = ["a", "b", "c", "d"].map(c);
  const s = organizar(r, new Map([["a", av(0)], ["c", av(3)]]), []);
  expect([...numeracao(s)]).toEqual([["c", 1], ["b", 2], ["d", 3], ["a", 4]]);
});

test("idsParaResposta corta em 25 e não inclui votadas", () => {
  const r = Array.from({ length: 30 }, (_, i) => c(`d${i}`));
  const m = new Map(r.map((d, i) => [d.id, av(i === 29 ? 0 : 3)] as [string, Avaliacao]));
  const s = organizar(r, m, ["d29"]);
  const resp = idsParaResposta(s, m);
  expect(resp).toHaveLength(25);
  expect(resp).not.toContain("d29");
  expect(resp[0]).toBe("d0");
});

test("voto sobrevive a filtro que esconde o card", () => {
  const todos = ["a", "b"].map(c);
  const m = new Map([["a", av(3)], ["b", av(0)]]);
  const votos = ["b"];
  expect(ids(organizar(todos.filter((d) => d.id !== "b"), m, votos).relacionadas)).toEqual(["a"]);
  expect(ids(organizar(todos, m, votos).relacionadas)).toEqual(["a", "b"]);
});
