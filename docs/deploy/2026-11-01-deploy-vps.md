# Runbook de deploy do JuriSight na VPS (MagnoHost)

Roteiro, na ordem e com os comandos, para colocar o JuriSight no ar numa VPS e mantê-lo
lá. Os arquivos de deploy já estão no repositório (`Dockerfile`, `frontend/Dockerfile`,
`docker-compose.prod.yml`, `deploy/`, `.env.production.example`, `.github/workflows/ci.yml`).
Em produção: **https://16-5-6-82.sslip.io** (VPS `16.5.6.82`, usuário `deploy`, app em
`/opt/jurisight`, com a `main` como branch de produção). O que mais pesa é o upload de
~7 GB de dados, na primeira carga.

Dados a levar para o servidor:

| Dado | Tamanho | Como vai |
|---|---|---|
| Postgres (`jurisight`) | 1,3 GB | `pg_dump` e `pg_restore` |
| Qdrant (2 coleções) | 4,8 GB | cópia do volume (mesma versão, v1.19.1) |
| Índice BM25 (`data/index/bm25s_index`) | 0,7 GB | `rsync` |
| Reranker de produção (`ms-marco-MultiBERT-L-12`) | 0,16 GB | `rsync` (os outros modelos do cache são do benchmark e não vão) |
| Modelo do Ollama (`llama3.2:3b`) | 2 GB | `ollama pull` no próprio servidor |

## 1. O que contratar

**Escolhido: MagnoHost, Servidor VPS 9950x BR 06 (6 vCPU Ryzen 9 9950X, 16 GB DDR5, 160 GB NVMe,
10 Gbps, Anti-DDoS), R$ 222,90/mês, sem adicionais.** Antes, a opção era a Runstack (CPU Pro, 8 vCPU,
R$ 297); a MagnoHost sai mais barata e com CPU mais rápida.

- **RAM:** em uso, o app ocupa de 8 a 10 GB: Llama 3B ~3 GB, BM25 ~2 a 3 GB, Qdrant ~1,5 GB, Postgres ~1 GB e o resto. Os 16 GB bastam.
- **CPU:** é o gargalo. O enriquecimento (Llama 3.2 3B no Ollama) e o reranker rodam em CPU. O Zen 5 tem núcleos rápidos e AVX-512, e os dois aproveitam isso.
- **Disco:** cerca de 25 GB ocupados dos 160 GB.

**Perguntar ao suporte antes de pagar:**
- Tem Ubuntu 24.04 LTS? É escolhido no painel depois da compra?
- O painel tem console de emergência (VNC)? Ele entra na VM sem passar pela rede e é a saída se uma configuração de SSH ou de firewall trancar o acesso.
- Há backup da VM? Confirmado: sim, guardado fora da VPS.

**Na instalação (painel da MagnoHost, VirtFusion):** cadastre antes a chave pública em "Chaves
SSH" e selecione-a. Depois: nome e hostname `jurisight-prod`, fuso `America/Sao_Paulo`, sistema
"Ubuntu Server 24.04 LTS (Noble Numbat) Minimal", IPv6 desligado, VNC ligado (console de
emergência) e DNS padrão.

**Na compra:**
- Ciclo mensal.
- Nenhum adicional.
- Sistema: Ubuntu 24.04 LTS.
- Se houver campo de chave SSH, cole `~/.ssh/id_ed25519.pub`. Se não houver, a seção 6 instala a chave com `ssh-copy-id`.

## 2. Como a infra fica montada

```
Internet ──TCP 443/80──> Caddy (HTTPS automático)
                           ├── /api/*  ──> api  (FastAPI :8000, prefixo /api removido)
                           └── /*      ──> web  (Next.js :3000)
Internet ──TCP 22──> sshd (só chave, sem root, fail2ban)
Rede interna do Docker, sem porta pública:
  api ──> postgres :5432 · qdrant :6333 · ollama :11434
```

Front e API ficam no mesmo domínio, então:
- o cookie de sessão funciona com `samesite=lax` e `COOKIE_SECURE=true`;
- `CORS_ORIGINS` recebe só `https://<DOMINIO>`;
- o front é compilado com `NEXT_PUBLIC_API_URL=https://<DOMINIO>/api`.

Postgres, Qdrant e Ollama não publicam porta nenhuma. A manutenção é feita de dentro, com `docker compose -f docker-compose.prod.yml exec postgres psql ...`.

**Portas visíveis de fora:** só 22 (SSH), 80 e 443. O Docker publica portas por cima do `ufw`:
uma porta publicada em 0.0.0.0 fica aberta para a internet mesmo com o firewall ligado. Por isso só
o Caddy publica portas.

### Camadas de proteção

| Camada | O que faz | Seção |
|---|---|---|
| Rede da MagnoHost | Anti-DDoS de até 20 Tbps (incluído) | — |
| Firewall (`ufw`) com bloqueio por padrão | só 22, 80 e 443 | 6 |
| SSH endurecido | só chave, sem senha, sem login de root, fail2ban | 6 |
| Docker sem portas públicas | bancos e Ollama só na rede interna do Docker | 4 |
| HTTPS | certificado Let's Encrypt automático pelo Caddy, com HSTS | 4 |
| App | sessão em cookie `httpOnly` + `Secure`; todas as rotas exigem login | já existe |
| Segredos | `.env` só no servidor, com permissão 600; senhas novas | 7 |
| Atualizações | `unattended-upgrades` para correções de segurança do sistema | 6 |
| Backup | backup da VM pela MagnoHost (fora da VPS) mais `pg_dump` diário | 11 |

## 3. Domínio e HTTPS

- **Sem domínio próprio hoje:** use `<IP-com-hífens>.sslip.io`, por exemplo `177-12-34-56.sslip.io`. O sslip.io resolve para o seu IP sem cadastro, e o Caddy emite o certificado sozinho.
- **Com domínio:** crie um registro A apontando para o IP da VPS e troque `DOMINIO`. O resto não muda.

## 4. Arquivos de deploy no repositório

| Arquivo | O que faz |
|---|---|
| `Dockerfile` | Imagem do backend: `python:3.13-slim` + `uv sync --frozen` sem os grupos de dev/benchmark, roda `uvicorn query.api.app:app --host 0.0.0.0 --port 8000`. A pasta `data/` entra como volume. |
| `frontend/Dockerfile` + `output: "standalone"` no `next.config.ts` | Build do Next com `ARG NEXT_PUBLIC_API_URL`; a imagem final roda só o `server.js`. |
| `docker-compose.prod.yml` | `name: jurisight` fixo e serviços `postgres`, `qdrant`, `ollama`, `api`, `web`, `caddy`. Só o Caddy publica portas (80/443); senha do Postgres pelo `.env`; `restart: unless-stopped`. |
| `deploy/Caddyfile` | `{$DOMINIO}`: `handle_path /api/*` → `api:8000`, o resto → `web:3000`, cabeçalhos de segurança (HSTS, `X-Content-Type-Options`, `Referrer-Policy`). |
| `.env.production.example` | Lista das variáveis de produção, sem valores. |
| `deploy/backup.sh` | `pg_dump` diário, guarda 7 dias em `/opt/backups`. |
| `.github/workflows/ci.yml` | Em todo PR e push: `pytest` do backend (sem `tests/test_api_stress.py`), `jest` e `next build` do front. Em push na `main`, com os dois verdes, o job `deploy` entra na VPS por SSH e roda `git pull --ff-only` e `docker compose -f docker-compose.prod.yml up -d --build`. |

Pronto quando: `docker compose -f docker-compose.prod.yml up --build` sobe tudo nesta máquina e
`https://localhost` abre o app (o teste local usa o certificado interno do Caddy).

## 5. Git

A `main` é a branch de produção: o que entra nela, com o CI verde, vai para a VPS.

## 6. Preparar a VPS

Se a compra não pediu chave SSH, instale a sua primeiro, desta máquina: `ssh-copy-id root@IP` (pede a senha de root do painel uma vez).

Como root, logo depois da entrega (`ssh root@IP`):

```bash
apt update && apt -y upgrade
# a imagem "Minimal" da MagnoHost vem sem estes pacotes
apt -y install curl git rsync ca-certificates nano
timedatectl set-timezone America/Sao_Paulo

# usuário de trabalho, com a mesma chave SSH do root
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
rsync -a ~/.ssh /home/deploy/ && chown -R deploy:deploy /home/deploy/.ssh
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

# SSH só por chave e sem root (teste "ssh deploy@IP" em OUTRO terminal antes de fechar esta sessão)
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

# firewall: só SSH, HTTP e HTTPS
apt -y install ufw fail2ban unattended-upgrades
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# swap de 4 GB, para picos de memória não derrubarem o app
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Docker + compose
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

Pronto quando: `ssh deploy@IP` entra sem senha, `ssh root@IP` é recusado e `docker run --rm hello-world` funciona.

## 7. Código e segredos no servidor

```bash
sudo mkdir -p /opt/jurisight /opt/backups && sudo chown deploy:deploy /opt/jurisight /opt/backups
git clone https://github.com/ViniciusZnt/JuriSight.git /opt/jurisight
cd /opt/jurisight && cp .env.production.example .env && chmod 600 .env && nano .env
```

| Variável | Valor |
|---|---|
| `DOMINIO` | `177-12-34-56.sslip.io` (ou o seu domínio) |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `DATABASE_URL` | `postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/jurisight` |
| `QDRANT_URL` | `http://qdrant:6333` |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `http://ollama:11434` / `llama3.2:3b` |
| `BM25_INDEX_PATH` | `/app/data/index/bm25s_index` |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` (novo: invalida as sessões locais) |
| `COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | `https://<DOMINIO>` |
| `API_RELOAD` | `false` |
| `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL` | os mesmos de hoje (a busca embute a consulta pela OpenAI) |
| `TYPESAFE_API_KEY`, `TYPESAFE_MODEL` | só se for rodar `classificar` no servidor; a busca não usa |

O `.env` nunca vai para o Git; ele existe só no servidor.

## 8. Copiar os dados (primeira carga)

> Este é o caminho da primeira carga, de uma máquina local para a VPS. O caminho de atualização é o pipeline Dagster (README, "Pipeline de dados (Dagster)").

Nesta máquina, em `~/JuriSight` (o WSL não tem `rsync`: instale antes com `sudo apt install -y rsync`):

```bash
mkdir -p ~/deploy-dados
docker exec jurisight_postgres pg_dump -U postgres -Fc jurisight > ~/deploy-dados/jurisight.dump
docker stop jurisight_qdrant      # volume parado = cópia consistente
docker run --rm -v jurisight_qdrant_data:/data -v ~/deploy-dados:/out alpine tar czf /out/qdrant.tgz -C /data .
docker start jurisight_qdrant
rsync -avP ~/deploy-dados/ deploy@IP:/opt/backups/inicial/
rsync -avP data/index/bm25s_index deploy@IP:/opt/jurisight/data/index/
rsync -avP data/index/reranker_cache/ms-marco-MultiBERT-L-12 deploy@IP:/opt/jurisight/data/index/reranker_cache/
```

O `rsync -P` retoma de onde parou se a conexão cair. Com 50 Mbps de upload, ~20 min; com 10 Mbps,
perto de 1h30.

Na VPS, em `/opt/jurisight`:

```bash
C="docker compose -f docker-compose.prod.yml"
$C create qdrant
docker run --rm -v jurisight_qdrant_data:/data -v /opt/backups/inicial:/in alpine sh -c "cd /data && tar xzf /in/qdrant.tgz"
$C up -d postgres && sleep 10
$C exec -T postgres pg_restore -U postgres -d jurisight --no-owner --clean --if-exists < /opt/backups/inicial/jurisight.dump
$C up -d ollama && $C exec ollama ollama pull llama3.2:3b
```

Pronto quando: `$C exec postgres psql -U postgres -d jurisight -c "select count(*) from documentos"` devolve 69349.

## 9. Subir o app

```bash
cd /opt/jurisight
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api   # espere "Application startup complete" (o BM25 leva 1 a 2 min)
```

## 10. Conferir o app

- [ ] `https://<DOMINIO>` abre, com cadeado válido.
- [ ] `curl https://<DOMINIO>/api/health` devolve `{"status":"ok"}`.
- [ ] Criar conta, entrar, fazer uma consulta com PDF e outra só com texto. A lista traz 20 resultados com o painel do provimento, e o detalhe abre.
- [ ] Enviar uma correção de provimento e apagar depois.
- [ ] No navegador, o cookie de sessão aparece como `Secure`.
- [ ] Desta máquina, `nmap -Pn <IP>` mostra só 22, 80 e 443.
- [ ] `free -h` e `docker stats`: memória abaixo de 14 GB com uma busca rodando.
- [ ] Anotar o tempo de uma busca completa: ele entra no TCC como latência em produção.

## 11. Backup

- A MagnoHost faz o backup da VM num armazenamento fora da VPS (confirmado com o suporte em 01/11).
- `pg_dump` diário: `crontab -e` no usuário `deploy` com `0 3 * * * /opt/jurisight/deploy/backup.sh`, que guarda 7 dias em `/opt/backups`.
- Os índices (Qdrant e BM25) só mudam quando a coleta ou a classificação roda de novo; a cópia de `/opt/backups/inicial` serve de base até lá.

## 12. CI/CD no GitHub

- **CI:** o `ci.yml` roda os testes e o `next build` em todo PR e push. O repositório é público, então o GitHub Actions é gratuito.
- **CD:** o job `deploy` do mesmo `ci.yml` roda depois dos testes verdes num push para a `main`. Ele entra na VPS por SSH e atualiza o app.

Para o CD funcionar:
1. Gere um par de chaves só para o GitHub: `ssh-keygen -t ed25519 -f ~/.ssh/jurisight_deploy -N ""`.
2. Coloque a pública na VPS, em `/home/deploy/.ssh/authorized_keys`.
3. No GitHub, em Settings → Secrets and variables → Actions, crie:
    - `VPS_HOST` = o IP;
    - `VPS_USER` = `deploy`;
    - `VPS_SSH_KEY` = o conteúdo da chave privada `~/.ssh/jurisight_deploy`.
4. Teste com um commit pequeno na `main` (no README, por exemplo).

Pronto quando: o check fica verde no PR e a alteração do teste aparece no site alguns minutos depois do merge.

## 13. Riscos e volta atrás

| Risco | O que fazer |
|---|---|
| Uma mudança no SSH ou no `ufw` tranca o acesso | Sempre testar o login em outro terminal antes de fechar a sessão atual; em último caso, o console do painel. |
| Busca lenta demais | Adicionar núcleos no painel (+R$ 20 por núcleo), ou tirar o reranker em produção (S2), que corta de 3 a 9 s por busca. |
| Memória estoura com o Llama carregado | O swap de 4 GB segura o pico. Se acontecer sempre, `OLLAMA_KEEP_ALIVE=5m` descarrega o modelo mais cedo. |
| Um deploy quebra o site | Na VPS, `git checkout <commit anterior>` e `docker compose -f docker-compose.prod.yml up -d --build`. Os dados ficam nos volumes. |
| Certificado não sai | Conferir se 80/443 estão abertas e se o domínio aponta para o IP; o erro aparece em `logs caddy`. |
| Upload dos dados cai | Rodar o mesmo `rsync -avP` de novo: ele continua de onde parou. |

A versão local continua funcionando com `./run.sh`; ela é o plano B para a banca.
