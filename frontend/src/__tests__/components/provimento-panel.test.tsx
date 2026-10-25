import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProvimentoPanel } from "@/components/provimento/provimento-panel";
import { ApiError, enviarCorrecaoProvimento, type ClassificacaoProvimento } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  enviarCorrecaoProvimento: jest.fn(),
}));

const enviar = enviarCorrecaoProvimento as jest.Mock;

const classificacao: ClassificacaoProvimento = {
  resultado: "nao_provido",
  recorrente: "reclamada",
  favorece: "reclamante",
  probabilidades: { resultado: { nao_provido: 0.82, parcialmente_provido: 0.15, provido: 0.03 } },
  confianca_resultado: 0.82,
  confianca_recorrente: 0.9,
  confianca_favorece: 0.7,
  modelo: "jev-1.13.0",
};

const renderPanel = (c: ClassificacaoProvimento | null = classificacao) =>
  render(<ProvimentoPanel documentoId="doc-1" provimento="NEGADO" classificacao={c} />);

beforeEach(() => enviar.mockReset());

describe("ProvimentoPanel", () => {
  it("mostra as três respostas", () => {
    renderPanel();
    expect(screen.getByText("Não provido")).toBeInTheDocument();
    expect(screen.getByText("Reclamada (empresa)")).toBeInTheDocument();
    expect(screen.getByText("Trabalhador")).toBeInTheDocument();
  });

  it("abre as probabilidades", async () => {
    renderPanel();
    await userEvent.click(screen.getAllByRole("button", { name: /ver probabilidades/i })[0]);
    expect(screen.getByText("Provido em parte")).toBeInTheDocument();
    expect(screen.getByText("15%")).toBeInTheDocument();
  });

  it("envia correção", async () => {
    enviar.mockResolvedValue({});
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /sugerir correção/i }));
    await userEvent.selectOptions(screen.getByLabelText("Resultado do recurso"), "parcialmente_provido");
    await userEvent.type(screen.getByLabelText(/comentário/i), "houve provimento parcial");
    await userEvent.click(screen.getByRole("button", { name: /enviar correção/i }));
    expect(enviar).toHaveBeenCalledWith("doc-1", {
      resultado: "parcialmente_provido",
      recorrente: "reclamada",
      favorece: "reclamante",
      comentario: "houve provimento parcial",
    });
    expect(await screen.findByText(/sua correção foi registrada/i)).toBeInTheDocument();
  });

  it("está correto envia as respostas do Jev", async () => {
    enviar.mockResolvedValue({});
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /está correto/i }));
    expect(enviar).toHaveBeenCalledWith("doc-1", {
      resultado: "nao_provido",
      recorrente: "reclamada",
      favorece: "reclamante",
      comentario: null,
    });
  });

  it("desabilita enviar durante o envio", async () => {
    enviar.mockReturnValue(new Promise(() => {}));
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /sugerir correção/i }));
    await userEvent.click(screen.getByRole("button", { name: /enviar correção/i }));
    expect(screen.getByRole("button", { name: /enviando/i })).toBeDisabled();
  });

  it("mostra erro da API", async () => {
    enviar.mockRejectedValue(new ApiError("Documento não encontrado.", 404));
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /está correto/i }));
    expect(await screen.findByText("Documento não encontrado.")).toBeInTheDocument();
  });

  it("sem classificação mostra o provimento simples e não oferece correção", () => {
    renderPanel(null);
    expect(screen.getByText(/ainda não classificado pela IA/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sugerir correção/i })).not.toBeInTheDocument();
  });

  it("não propaga o clique para o card", async () => {
    const pai = jest.fn();
    render(
      <div onClick={pai}>
        <ProvimentoPanel documentoId="doc-1" provimento="NEGADO" classificacao={classificacao} compacto />
      </div>
    );
    await userEvent.click(screen.getByRole("button", { name: /detalhes do provimento/i }));
    expect(pai).not.toHaveBeenCalled();
  });
});
