import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "@/components/sidebar";
import type { Conversation } from "@/lib/conversations";

const rename = jest.fn();
const conversa: Conversation = { id: "c1", title: "Horas extras", createdAt: Date.now(), versions: [] };

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), prefetch: jest.fn() }),
  usePathname: () => "/",
}));
jest.mock("@/lib/conversations", () => ({
  ...jest.requireActual("@/lib/conversations"),
  useConversations: () => ({ conversations: [conversa], activeId: null, rename, remove: jest.fn(), setActive: jest.fn() }),
}));
jest.mock("@/lib/search-session", () => ({ useSearchSession: () => ({ loadVersion: jest.fn() }) }));
jest.mock("@/lib/auth", () => ({ useAuth: () => ({ logout: jest.fn() }) }));
jest.mock("@/lib/profile", () => ({
  ...jest.requireActual("@/lib/profile"),
  useProfile: () => ({ profile: { name: "Ana Lima", email: "ana@exemplo.invalid", phone: "", oab: "", role: "Advogado" } }),
}));

beforeEach(() => rename.mockReset());

const abrirMenu = () => userEvent.click(screen.getByRole("button", { name: 'Opções de "Horas extras"' }));

describe("Sidebar", () => {
  it("Renomear põe o foco no campo, já com o título, e Enter salva", async () => {
    render(<Sidebar />);
    await abrirMenu();
    await userEvent.click(screen.getByText("Renomear"));
    const campo = screen.getByDisplayValue("Horas extras");
    expect(campo).toHaveFocus();
    await userEvent.clear(campo);
    await userEvent.type(campo, "Horas extras bancárias{Enter}");
    expect(rename).toHaveBeenCalledWith("c1", "Horas extras bancárias");
  });

  it("o fundo do menu fecha o menu ao ser clicado", async () => {
    render(<Sidebar />);
    await abrirMenu();
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fechar menu" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
