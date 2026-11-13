import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "@/components/login/login-page";
import { RegisterPage } from "@/components/login/register-page";
import { ApiError, registrarUsuario } from "@/lib/api";

const push = jest.fn();
const login = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
jest.mock("@/lib/auth", () => ({ useAuth: () => ({ login }) }));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  registrarUsuario: jest.fn(),
}));
const registrar = registrarUsuario as jest.Mock;

beforeEach(() => {
  push.mockReset();
  login.mockReset();
  registrar.mockReset();
});

const digitar = (placeholder: string | RegExp, texto: string) =>
  userEvent.type(screen.getByPlaceholderText(placeholder), texto);

describe("Login", () => {
  it("mostra título, campos e deixa o envio desabilitado enquanto vazio", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "JuriSight" })).toBeInTheDocument();
    expect(screen.getByText("Pesquisa contextual de jurisprudência trabalhista")).toBeInTheDocument();
    expect(screen.getByText("E-mail")).toBeInTheDocument();
    expect(screen.getByText("Senha")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /entrar/i })).toBeDisabled();
  });

  it("alterna mostrar/ocultar senha", async () => {
    render(<LoginPage />);
    const senha = screen.getByPlaceholderText("••••••••");
    expect(senha).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(senha).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(senha).toHaveAttribute("type", "password");
  });

  it("entra com os valores digitados e vai para a Home", async () => {
    login.mockResolvedValue(undefined);
    render(<LoginPage />);
    await digitar("voce@escritorio.com.br", " ana@exemplo.com ");
    await digitar("••••••••", "segredo123");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(login).toHaveBeenCalledWith("ana@exemplo.com", "segredo123");
    expect(push).toHaveBeenCalledWith("/");
  });

  it("mostra a mensagem da API quando o login falha e não navega", async () => {
    login.mockRejectedValue(new ApiError("Credenciais inválidas.", 401));
    render(<LoginPage />);
    await digitar("voce@escritorio.com.br", "ana@exemplo.com");
    await digitar("••••••••", "errada");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(await screen.findByText("Credenciais inválidas.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("usa a mensagem padrão para erro desconhecido", async () => {
    login.mockRejectedValue(new Error("rede"));
    render(<LoginPage />);
    await digitar("voce@escritorio.com.br", "ana@exemplo.com");
    await digitar("••••••••", "x");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(await screen.findByText("Não foi possível entrar. Tente novamente.")).toBeInTheDocument();
  });

  it("desabilita o botão e mostra 'Entrando…' durante o envio", async () => {
    login.mockReturnValue(new Promise(() => {}));
    render(<LoginPage />);
    await digitar("voce@escritorio.com.br", "ana@exemplo.com");
    await digitar("••••••••", "x");
    await userEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(screen.getByRole("button", { name: "Entrando…" })).toBeDisabled();
  });

  it("leva às telas de recuperação e de cadastro", async () => {
    render(<LoginPage />);
    await userEvent.click(screen.getByRole("button", { name: "Esqueceu a senha?" }));
    expect(push).toHaveBeenLastCalledWith("/esqueci-senha");
    await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
    expect(push).toHaveBeenLastCalledWith("/registro");
  });
});

describe("Cadastro", () => {
  const preencher = async (senha = "senha-boa-123", confirma = senha) => {
    await digitar("Seu nome", " Ana Souza ");
    await digitar("voce@escritorio.com.br", "ana@exemplo.com");
    await digitar(/Mínimo 8/, senha);
    await digitar("Repita a senha", confirma);
  };

  it("mostra título, campos e deixa o envio desabilitado enquanto vazio", () => {
    render(<RegisterPage />);
    expect(screen.getByRole("heading", { name: "Criar conta" })).toBeInTheDocument();
    expect(screen.getByText("Cadastro de advogados e assistentes jurídicos")).toBeInTheDocument();
    for (const rotulo of ["Nome completo", "E-mail", "Senha", "Confirmar senha"]) {
      expect(screen.getByText(rotulo)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /criar conta/i })).toBeDisabled();
  });

  it("o olho mostra/oculta as duas senhas ao mesmo tempo", async () => {
    render(<RegisterPage />);
    const nova = screen.getByPlaceholderText(/Mínimo 8/);
    const confirma = screen.getByPlaceholderText("Repita a senha");
    await userEvent.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(nova).toHaveAttribute("type", "text");
    expect(confirma).toHaveAttribute("type", "text");
  });

  it("avisa senha curta e senhas diferentes e mantém o envio desabilitado", async () => {
    render(<RegisterPage />);
    await preencher("curta", "outra");
    expect(screen.getByText("A senha precisa ter pelo menos 8 caracteres.")).toBeInTheDocument();
    expect(screen.getByText("As senhas não coincidem.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /criar conta/i })).toBeDisabled();
  });

  it("registra, entra automaticamente e vai para a Home", async () => {
    registrar.mockResolvedValue(undefined);
    login.mockResolvedValue(undefined);
    render(<RegisterPage />);
    await preencher();
    await userEvent.click(screen.getByRole("button", { name: /criar conta/i }));
    expect(registrar).toHaveBeenCalledWith({ email: "ana@exemplo.com", password: "senha-boa-123", nome: "Ana Souza" });
    expect(login).toHaveBeenCalledWith("ana@exemplo.com", "senha-boa-123");
    expect(push).toHaveBeenCalledWith("/");
  });

  it("mostra a mensagem da API quando o cadastro falha", async () => {
    registrar.mockRejectedValue(new ApiError("E-mail já cadastrado.", 409));
    render(<RegisterPage />);
    await preencher();
    await userEvent.click(screen.getByRole("button", { name: /criar conta/i }));
    expect(await screen.findByText("E-mail já cadastrado.")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("tem o link de volta para o login", async () => {
    render(<RegisterPage />);
    await userEvent.click(screen.getByRole("button", { name: /já tem conta\? entrar/i }));
    expect(push).toHaveBeenCalledWith("/login");
  });
});
