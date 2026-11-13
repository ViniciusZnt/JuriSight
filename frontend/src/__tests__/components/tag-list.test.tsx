import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { TagList } from "@/components/revisao/entity-review-page";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }), useSearchParams: () => new URLSearchParams() }));

function Harness({ inicial }: { inicial: string[] }) {
  const [items, setItems] = useState(inicial);
  return <TagList items={items} onChange={setItems} placeholder="Novo…" />;
}

const chip = (nome: string) => screen.getByText(nome).closest("div.group") as HTMLElement;

test("remover o 1º de 3 chips mantém cada um dos outros no seu próprio elemento", async () => {
  jest.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
  render(<Harness inicial={["A", "B", "C"]} />);
  const b = chip("B");
  const c = chip("C");

  await user.click(screen.getByLabelText("Remover A"));
  act(() => {
    jest.advanceTimersByTime(300);
  });

  expect(screen.queryByText("A")).toBeNull();
  // com key=índice, o elemento de B passava a mostrar C (e o de C era destruído)
  expect(chip("B")).toBe(b);
  expect(chip("C")).toBe(c);
  jest.useRealTimers();
});

test("chips repetidos continuam com chaves distintas", () => {
  render(<Harness inicial={["A", "A"]} />);
  expect(screen.getAllByText("A")).toHaveLength(2);
});
