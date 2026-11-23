import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileTab } from "@/components/configuracoes/profile-tab";
import { SettingsTabs } from "@/components/configuracoes/settings-tabs";
import { ThemeToggle } from "@/components/settings/theme-toggle";
import type { Profile } from "@/lib/profile";

const update = jest.fn();
let perfil: Profile = { name: "Ana Maria Lima", email: "ana@exemplo.invalid", phone: "", oab: "", role: "Advogado" };
let hidratado = true;

jest.mock("@/lib/profile", () => ({
  ...jest.requireActual("@/lib/profile"),
  useProfile: () => ({ profile: perfil, hydrated: hidratado, update }),
}));
jest.mock("@/components/configuracoes/account-tab", () => ({ AccountTab: () => <p>aba conta</p> }));

beforeEach(() => {
  jest.clearAllMocks();
  perfil = { name: "Ana Maria Lima", email: "ana@exemplo.invalid", phone: "", oab: "", role: "Advogado" };
  hidratado = true;
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});
afterEach(() => jest.useRealTimers());

describe("ProfileTab", () => {
  it("mostra iniciais e dados da conta só para leitura; salvar começa desabilitado", () => {
    render(<ProfileTab />);
    expect(screen.getByText("AL")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Nome/)).toHaveAttribute("readonly");
    expect(screen.getByRole("button", { name: "Salvar alterações" })).toBeDisabled();
  });

  it("edita telefone, OAB e papel e salva; mostra 'Salvo' por 2 s", async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    update.mockResolvedValue(undefined);
    render(<ProfileTab />);
    await user.type(screen.getByLabelText(/Telefone/), "48999990000");
    await user.type(screen.getByLabelText(/Número da OAB/), "123/SC");
    await user.click(screen.getByRole("button", { name: "Assistente Jurídica" }));
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
    expect(update).toHaveBeenCalledWith({ phone: "48999990000", oab: "123/SC", role: "Assistente Jurídica" });
    expect(await screen.findByText("Salvo")).toBeInTheDocument();
    act(() => jest.advanceTimersByTime(2000));
    expect(screen.queryByText("Salvo")).not.toBeInTheDocument();
  });

  it("erro ao salvar aparece como alerta (mensagem do erro ou a genérica)", async () => {
    update.mockRejectedValueOnce(new Error("OAB inválida."));
    render(<ProfileTab />);
    await userEvent.type(screen.getByLabelText(/Número da OAB/), "x");
    await userEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("OAB inválida.");

    update.mockRejectedValueOnce("falhou");
    await userEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível salvar o perfil.");
  });

  it("enquanto salva mostra 'Salvando…' e não envia duas vezes", async () => {
    update.mockReturnValue(new Promise(() => {}));
    render(<ProfileTab />);
    await userEvent.type(screen.getByLabelText(/Telefone/), "1");
    await userEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    expect(screen.getByRole("button", { name: "Salvando…" })).toBeDisabled();
    expect(update).toHaveBeenCalledTimes(1);
  });

  it("quando o perfil real chega (hydrated), o rascunho é sincronizado", () => {
    hidratado = false;
    const { rerender } = render(<ProfileTab />);
    perfil = { ...perfil, oab: "999/SC" };
    hidratado = true;
    rerender(<ProfileTab />);
    expect(screen.getByLabelText(/Número da OAB/)).toHaveValue("999/SC");
    expect(screen.getByRole("button", { name: "Salvar alterações" })).toBeDisabled();
  });
});

describe("ThemeToggle", () => {
  it("lê o tema atual e alterna, gravando no localStorage", async () => {
    document.documentElement.classList.add("dark");
    render(<ThemeToggle />);
    const chave = screen.getByRole("switch");
    expect(chave).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Ativado")).toBeInTheDocument();
    await userEvent.click(chave);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("jurisight:theme")).toBe("light");
    await userEvent.click(chave);
    expect(localStorage.getItem("jurisight:theme")).toBe("dark");
    expect(screen.getByText("Ativado")).toBeInTheDocument();
  });

  it("sem localStorage, ainda alterna o tema", async () => {
    const setItem = jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    render(<ThemeToggle />);
    await userEvent.click(screen.getByRole("switch"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    setItem.mockRestore();
  });
});

describe("SettingsTabs", () => {
  it("abre em Perfil e troca para Aparência e Conta", async () => {
    render(<SettingsTabs />);
    expect(screen.getByLabelText(/Telefone/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aparência" }));
    expect(screen.getByRole("switch")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Conta" }));
    expect(screen.getByText("aba conta")).toBeInTheDocument();
  });
});
