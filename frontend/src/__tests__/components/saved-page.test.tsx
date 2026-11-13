import { render, screen } from "@testing-library/react";
import { SavedPage } from "@/components/salvos/saved-page";
import type { SavedDecision } from "@/lib/saved";

let salvos: SavedDecision[] = [];
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/lib/saved", () => ({ useSaved: () => ({ saved: salvos, toggle: jest.fn() }) }));

const salvo = (date: string): SavedDecision => ({
  id: "1", title: "Título", court: "TRT-2", chamber: "1ª Turma", date, outcome: "favorable",
  relevance: 90, rapporteur: "Fulano", processNumber: "000123", savedAt: 0,
});

const fusoOriginal = process.env.TZ;
beforeAll(() => { process.env.TZ = "America/Sao_Paulo"; });
afterAll(() => { process.env.TZ = fusoOriginal; });

test("a data só com dia (yyyy-mm-dd) aparece no mesmo dia do calendário, não no anterior", () => {
  salvos = [salvo("2025-12-17")];
  render(<SavedPage />);
  expect(screen.getByText(/2025/)).toHaveTextContent(/^17 de dez\.? de 2025$/i);
});

test("data vazia não vira 'Invalid Date'", () => {
  salvos = [salvo("")];
  render(<SavedPage />);
  expect(screen.queryByText(/Invalid Date/)).toBeNull();
  expect(screen.getByText("Data não informada")).toBeInTheDocument();
});
