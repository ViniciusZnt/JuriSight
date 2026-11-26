#!/usr/bin/env bash
# Instala na VPS o runner self-hosted do GitHub Actions que faz o deploy (CD sem SSH de entrada:
# o runner busca os jobs no GitHub por HTTPS). Roteiro completo em
# docs/deploy/2026-11-01-deploy-vps.md, seção "CI/CD no GitHub".
#
# ANTES de rodar (o repositório é público): em Settings → Actions → General → "Fork pull request
# workflows from outside collaborators", marque "Require approval for all outside collaborators".
# Sem isso, um PR de fork pode mudar o workflow e rodar código nesta máquina.
#
# Uso, na VPS, como o usuário deploy:
#   /opt/jurisight/deploy/instalar-runner.sh <TOKEN>
# O TOKEN sai de Settings → Actions → Runners → New self-hosted runner (Linux; vale 1 hora).
set -euo pipefail

VERSAO=2.338.2
SHA256=baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40
REPO=https://github.com/ViniciusZnt/JuriSight
DIR=/opt/actions-runner
NOME=jurisight-vps
LABEL=jurisight-producao   # o job deploy do ci.yml pede [self-hosted, jurisight-producao]

token="${1:?uso: $0 <TOKEN de registro do runner>}"

if [[ "$(id -un)" != "deploy" ]]; then
    echo "Rode como o usuário deploy (o mesmo dono de /opt/jurisight)." >&2
    exit 1
fi
if ! id -nG | grep -qw docker; then
    echo "O usuário deploy precisa estar no grupo docker (o deploy roda docker compose)." >&2
    exit 1
fi

sudo mkdir -p "$DIR"
sudo chown deploy:deploy "$DIR"
cd "$DIR"

if [[ ! -x ./config.sh ]]; then
    arquivo="actions-runner-linux-x64-$VERSAO.tar.gz"
    # Só HTTPS, inclusive nos redirecionamentos (o download da release redireciona para outro host).
    curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 -o "$arquivo" \
        "https://github.com/actions/runner/releases/download/v$VERSAO/$arquivo"
    echo "$SHA256  $arquivo" | sha256sum -c -
    tar xzf "$arquivo"
    rm "$arquivo"
fi

./config.sh --unattended --replace --url "$REPO" --token "$token" \
    --name "$NOME" --labels "$LABEL" --work _work

# Serviço do systemd, rodando como deploy e subindo junto com a VPS.
sudo ./svc.sh install deploy
sudo ./svc.sh start
sudo ./svc.sh status --no-pager || true

echo
echo "Pronto. Confira em Settings → Actions → Runners: '$NOME' deve aparecer como Idle."
