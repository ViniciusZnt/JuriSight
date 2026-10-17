import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RotulacaoPage } from "@/components/avaliacao/rotulacao-page";
import { ApiError, emptyEstrutura, type FilaAvaliacao } from "@/lib/api";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  obterFilaAvaliacao: jest.fn(),
  enviarRotulo: jest.fn(),
}));

const obterFila = api.obterFilaAvaliacao as jest.Mock;
const enviar = api.enviarRotulo as jest.Mock;

function fila(id: string, feitos = 0, total = 150): FilaAvaliacao {
  return {
    par: {
      id,
      tese: {
        ...emptyEstrutura(),
        pedido_principal: "Adicional de insalubridade",
        tese_central: "Exposição a agente químico sem EPI eficaz",
        normas: ["NR-15", "CLT art. 192"],
      },
      documento: {
        id: `doc-${id}`,
        ementa: "EMENTA do acórdão de teste",
        fundamentacao_inicio: "Trecho da fundamentação",
        link_original: "https://exemplo.test/inteiro-teor",
        numero_processo: "RR-100-44.2021.5.01.0019",
        tribunal: "TST",
      },
    },
    feitos,
    total,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
});

describe("RotulacaoPage", () => {
  it("envia_rotulo_com_atalhos", async () => {
    obterFila.mockResolvedValueOnce(fila("p1", 0)).mockResolvedValueOnce(fila("p2", 1));
    enviar.mockResolvedValue(undefined);
    render(<RotulacaoPage />);

    expect(await screen.findByText("EMENTA do acórdão de teste")).toBeInTheDocument();
    expect(screen.getByText("0 de 150")).toBeInTheDocument();

    await userEvent.keyboard("3");
    await userEvent.keyboard("F");

    await waitFor(() => expect(enviar).toHaveBeenCalledWith("p1", 2, "fortalece"));
    expect(enviar).toHaveBeenCalledTimes(1);
    // carrega o próximo par e limpa a seleção
    expect(await screen.findByText("1 de 150")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mesmo pedido/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("clicar_nos_botoes_tem_o_mesmo_efeito", async () => {
    obterFila.mockResolvedValueOnce(fila("p1")).mockResolvedValueOnce(fila("p2", 1));
    enviar.mockResolvedValue(undefined);
    render(<RotulacaoPage />);

    await userEvent.click(await screen.findByRole("button", { name: /Nada a ver/ }));
    await userEvent.click(screen.getByRole("button", { name: "Enfraquece" }));
    await waitFor(() => expect(enviar).toHaveBeenCalledWith("p1", 0, "enfraquece"));
  });

  it("mostra_tudo_rotulado_quando_fila_vazia", async () => {
    obterFila.mockResolvedValueOnce({ par: null, feitos: 150, total: 150 });
    render(<RotulacaoPage />);
    expect(await screen.findByText("Tudo rotulado. Obrigado!")).toBeInTheDocument();
  });

  it("mostra_acesso_restrito_em_403", async () => {
    obterFila.mockRejectedValueOnce(new ApiError("Acesso restrito à avaliação.", 403));
    render(<RotulacaoPage />);
    expect(await screen.findByText("Acesso restrito à avaliação.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tentar de novo" })).not.toBeInTheDocument();
  });

  it("mostra_erro_com_tentar_de_novo", async () => {
    obterFila.mockRejectedValueOnce(new ApiError("Falha", 500)).mockResolvedValueOnce(fila("p1"));
    render(<RotulacaoPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("EMENTA do acórdão de teste")).toBeInTheDocument();
  });

  it("nao_envia_com_so_um_eixo_escolhido", async () => {
    obterFila.mockResolvedValueOnce(fila("p1"));
    render(<RotulacaoPage />);
    await screen.findByText("EMENTA do acórdão de teste");

    await userEvent.keyboard("3");
    expect(enviar).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Mesmo pedido/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("ignora_atalhos_com_modificador", async () => {
    obterFila.mockResolvedValueOnce(fila("p1"));
    render(<RotulacaoPage />);
    await screen.findByText("EMENTA do acórdão de teste");

    await userEvent.keyboard("{Control>}3{/Control}");
    expect(screen.getByRole("button", { name: /Mesmo pedido/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("mantem_selecao_e_mostra_erro_quando_o_envio_falha", async () => {
    obterFila.mockResolvedValueOnce(fila("p1"));
    enviar.mockRejectedValueOnce(new ApiError("Par fora da amostra.", 404));
    render(<RotulacaoPage />);
    await screen.findByText("EMENTA do acórdão de teste");

    await userEvent.keyboard("4");
    await userEvent.keyboard("n");

    expect(await screen.findByText("Par fora da amostra.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mesmo caso/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Neutro" })).toHaveAttribute("aria-pressed", "true");
  });

  it("bloqueia_envio_duplo_enquanto_o_post_esta_em_andamento", async () => {
    obterFila.mockResolvedValueOnce(fila("p1")).mockResolvedValueOnce(fila("p2", 1));
    let resolver: () => void = () => {};
    enviar.mockReturnValueOnce(new Promise<void>((r) => (resolver = r)));
    render(<RotulacaoPage />);
    await screen.findByText("EMENTA do acórdão de teste");

    await userEvent.keyboard("2");
    await userEvent.keyboard("e");
    await userEvent.keyboard("1");
    await userEvent.keyboard("f");
    expect(enviar).toHaveBeenCalledTimes(1);
    expect(enviar).toHaveBeenCalledWith("p1", 1, "enfraquece");

    resolver();
    expect(await screen.findByText("1 de 150")).toBeInTheDocument();
  });

  it("tecla_durante_o_carregamento_do_proximo_par_nao_vaza_a_selecao", async () => {
    let entregarProximo: (f: FilaAvaliacao) => void = () => {};
    obterFila
      .mockResolvedValueOnce(fila("p1"))
      .mockReturnValueOnce(new Promise<FilaAvaliacao>((r) => (entregarProximo = r)));
    enviar.mockResolvedValue(undefined);
    render(<RotulacaoPage />);
    await screen.findByText("EMENTA do acórdão de teste");

    await userEvent.keyboard("3");
    await userEvent.keyboard("f");
    await waitFor(() => expect(enviar).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(obterFila).toHaveBeenCalledTimes(2));

    // o POST terminou, mas o próximo par ainda não chegou
    await userEvent.keyboard("4");
    await userEvent.keyboard("n");

    entregarProximo(fila("p2", 1));
    expect(await screen.findByText("1 de 150")).toBeInTheDocument();
    expect(enviar).toHaveBeenCalledTimes(1);
    expect(screen.queryAllByRole("button", { pressed: true })).toHaveLength(0);
  });

  it("link_do_inteiro_teor_abre_em_nova_aba", async () => {
    obterFila.mockResolvedValueOnce(fila("p1"));
    render(<RotulacaoPage />);
    const link = await screen.findByRole("link", { name: /Ver inteiro teor/ });
    expect(link).toHaveAttribute("href", "https://exemplo.test/inteiro-teor");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
