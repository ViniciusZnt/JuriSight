import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ForgotPasswordPage } from "@/components/login/forgot-password-page";
import { ResetPasswordPage } from "@/components/login/reset-password-page";
import { ApiError, pedirRedefinicaoSenha, redefinirSenha } from "@/lib/api";

let mockToken: string | null = "tok-123";
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => ({ get: () => mockToken }),
}));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  pedirRedefinicaoSenha: jest.fn(),
  redefinirSenha: jest.fn(),
}));
const pedir = pedirRedefinicaoSenha as jest.Mock;
const redefinir = redefinirSenha as jest.Mock;

beforeEach(() => {
  mockToken = "tok-123";
  pedir.mockReset();
  redefinir.mockReset();
});

describe("Esqueci minha senha (issue #14)", () => {
  it("pede o link ao backend e só então mostra 'verifique seu e-mail'", async () => {
    pedir.mockResolvedValue(undefined);
    render(<ForgotPasswordPage />);
    await userEvent.type(screen.getByPlaceholderText("voce@escritorio.com.br"), "ana@exemplo.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar link/i }));
    expect(pedir).toHaveBeenCalledWith("ana@exemplo.com");
    expect(await screen.findByText(/verifique seu e-mail/i)).toBeInTheDocument();
  });

  it("sem envio de e-mail no servidor, mostra o aviso e não finge que enviou", async () => {
    pedir.mockRejectedValue(new ApiError("A recuperação de senha por e-mail ainda não está disponível.", 503));
    render(<ForgotPasswordPage />);
    await userEvent.type(screen.getByPlaceholderText("voce@escritorio.com.br"), "ana@exemplo.com");
    await userEvent.click(screen.getByRole("button", { name: /enviar link/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ainda não está disponível");
    expect(screen.queryByText(/verifique seu e-mail/i)).not.toBeInTheDocument();
  });
});

describe("Redefinir senha (issue #14)", () => {
  const preencher = async (senha: string) => {
    const [nova, confirma] = screen.getAllByPlaceholderText(/caracteres|repita|confirme/i);
    await userEvent.type(nova, senha);
    await userEvent.type(confirma, senha);
  };

  it("manda o token do link com a senha nova", async () => {
    redefinir.mockResolvedValue(undefined);
    render(<ResetPasswordPage />);
    await preencher("senha-nova-123");
    await userEvent.click(screen.getByRole("button", { name: /redefinir senha/i }));
    expect(redefinir).toHaveBeenCalledWith("tok-123", "senha-nova-123");
    expect(await screen.findByText("Senha redefinida")).toBeInTheDocument();
  });

  it("link vencido ou já usado: mostra o motivo e não diz que deu certo", async () => {
    redefinir.mockRejectedValue(new ApiError("Este link é inválido, expirou ou já foi usado.", 400));
    render(<ResetPasswordPage />);
    await preencher("senha-nova-123");
    await userEvent.click(screen.getByRole("button", { name: /redefinir senha/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("expirou ou já foi usado");
    expect(screen.queryByText("Senha redefinida")).not.toBeInTheDocument();
  });

  it("sem token no endereço, avisa e não deixa enviar", () => {
    mockToken = null;
    render(<ResetPasswordPage />);
    expect(screen.getByRole("alert")).toHaveTextContent(/não tem o link de redefinição/);
    expect(screen.getByRole("button", { name: /redefinir senha/i })).toBeDisabled();
  });
});
