#!/usr/bin/env bash
# Sobe o JuriSight inteiro com um comando só: infra (Postgres/Ollama/Qdrant via
# docker compose) + backend (FastAPI) + frontend (Next.js).
#
# Uso:
#   ./run.sh              # sobe tudo, fica em foreground, Ctrl+C para backend+frontend
#   ./run.sh --logs       # depois de subir, mostra os logs ao vivo (tail -f)
#
# Infra (docker compose) fica no ar mesmo depois do Ctrl+C — não é o script que
# sobe/derruba isso a cada execução. Pra derrubar a infra também: `docker compose down`.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# Cores só pra facilitar leitura no terminal.
c_azul='\033[0;34m'; c_verde='\033[0;32m'; c_amarelo='\033[0;33m'; c_vermelho='\033[0;31m'; c_reset='\033[0m'
info()  { echo -e "${c_azul}==>${c_reset} $*"; }
ok()    { echo -e "${c_verde}✓${c_reset} $*"; }
avisa() { echo -e "${c_amarelo}!${c_reset} $*"; }
erro()  { echo -e "${c_vermelho}✗${c_reset} $*" >&2; }

BACKEND_PID=""
FRONTEND_PID=""

# Mata backend/frontend (deste script) ao sair — a infra do docker compose fica no ar
# de propósito, é serviço compartilhado, não algo pra derrubar toda hora.
cleanup() {
    echo
    info "Encerrando…"
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    ok "Backend e frontend parados. Infra (postgres/ollama/qdrant) continua no ar — 'docker compose down' pra derrubar também."
    exit 0
}
trap cleanup INT TERM

espera_http() {
    # espera_http <url> <rótulo> <timeout_s> <dica-de-por-que-demora>
    # -m 15 (não 2) no curl: o primeiro request ao Next.js dev dispara a
    # compilação on-demand da página e a resposta só volta quando termina —
    # um timeout curto aqui derruba um serviço que só estava compilando.
    local url="$1" rotulo="$2" timeout="${3:-180}" dica="${4:-}" decorrido=0
    while ! curl -s -o /dev/null -m 15 "$url"; do
        sleep 3
        decorrido=$((decorrido + 3))
        if [ "$decorrido" -ge "$timeout" ]; then
            return 1
        fi
        if [ $((decorrido % 20)) -lt 3 ]; then
            avisa "ainda esperando $rotulo… (${decorrido}s${dica:+ — $dica})"
        fi
    done
    return 0
}

# --------------------------------------------------------------------------- #
# 1) .env — precisa existir com o essencial preenchido                        #
# --------------------------------------------------------------------------- #
if [ ! -f .env ]; then
    erro ".env não existe. Rode: cp .env.example .env — e preencha OPENAI_API_KEY e JWT_SECRET_KEY."
    exit 1
fi
set -a; source .env; set +a

if [ -z "${OPENAI_API_KEY:-}" ] || [ "${OPENAI_API_KEY:-}" = "sk-..." ]; then
    erro "OPENAI_API_KEY não está preenchida no .env (obrigatória, com crédito pré-pago)."
    exit 1
fi
if [ -z "${JWT_SECRET_KEY:-}" ]; then
    erro "JWT_SECRET_KEY não está preenchida no .env. Gere uma: openssl rand -hex 32"
    exit 1
fi

# --------------------------------------------------------------------------- #
# 2) Infra — Postgres, Ollama, Qdrant                                         #
# --------------------------------------------------------------------------- #
info "Subindo infra (postgres, ollama, qdrant)…"
docker compose up -d

info "Esperando Postgres ficar saudável…"
decorrido=0
while [ "$(docker inspect -f '{{.State.Health.Status}}' jurisight_postgres 2>/dev/null)" != "healthy" ]; do
    sleep 2; decorrido=$((decorrido + 2))
    if [ "$decorrido" -ge 60 ]; then erro "Postgres não ficou saudável em 60s."; exit 1; fi
done
ok "Postgres no ar."

info "Conferindo modelos do Ollama (baixa só o que faltar — pode demorar na primeira vez)…"
modelos_atuais="$(curl -s -m 5 http://localhost:11434/api/tags 2>/dev/null || echo '')"
for modelo in nomic-embed-text llama3.2:3b; do
    if echo "$modelos_atuais" | grep -q "\"${modelo%%:*}"; then
        ok "Modelo $modelo já presente."
    else
        avisa "Baixando $modelo (pode levar alguns minutos)…"
        docker exec jurisight_ollama ollama pull "$modelo"
    fi
done

# --------------------------------------------------------------------------- #
# 3) Backend — FastAPI                                                        #
# --------------------------------------------------------------------------- #
if curl -s -o /dev/null -m 2 http://localhost:8000/health; then
    avisa "Backend já está respondendo em :8000 — não subi outro (evita dois processos disputando a porta)."
else
    info "Subindo backend (uv run python main.py)…"
    nohup uv run python main.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    info "Esperando o backend responder…"
    if ! espera_http "http://localhost:8000/health" "backend" 240 "normal, o primeiro boot recarrega o índice BM25 de ~1GB"; then
        erro "Backend não subiu em 240s. Últimas linhas do log:"
        tail -30 "$BACKEND_LOG"
        cleanup
    fi
    ok "Backend no ar (PID $BACKEND_PID) — http://localhost:8000"
fi

# --------------------------------------------------------------------------- #
# 4) Frontend — Next.js                                                       #
# --------------------------------------------------------------------------- #
if curl -s -o /dev/null -m 2 http://localhost:3000; then
    avisa "Frontend já está respondendo em :3000 — não subi outro."
else
    info "Subindo frontend (next dev)…"
    # Chama o binário do Next direto (não `npm run dev`): o npm não repassa
    # SIGTERM pro processo filho que ele spawna, então matar o PID do `npm`
    # deixaria o `next dev` real órfão e vivo — Ctrl+C pareceria funcionar mas
    # o servidor continuaria rodando na porta.
    ( cd frontend && exec ./node_modules/.bin/next dev ) > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    # Timeout longo de propósito: o primeiro GET dispara a compilação on-demand
    # da página no Next dev (mais lento ainda em disco lento) — isso NÃO é um
    # erro fatal como o backend não subir, então só avisa e segue (o processo
    # continua no ar e provavelmente fica pronto segundos depois).
    if ! espera_http "http://localhost:3000" "frontend" 120 "normal, a 1ª página compila sob demanda"; then
        avisa "Frontend ainda não respondeu em 120s — pode estar compilando a 1ª página num disco lento."
        avisa "Não vou derrubar o backend por causa disso. Acompanhe: tail -f $FRONTEND_LOG"
    else
        ok "Frontend no ar (PID $FRONTEND_PID) — http://localhost:3000"
    fi
fi

echo
ok "Tudo no ar:"
echo "    Frontend:  http://localhost:3000"
echo "    Backend:   http://localhost:8000  (docs em /docs)"
echo "    Qdrant:    http://localhost:6333/dashboard"
echo "    Logs:      $BACKEND_LOG · $FRONTEND_LOG"
echo
info "Ctrl+C encerra backend e frontend (a infra do docker compose continua no ar)."

if [ "${1:-}" = "--logs" ]; then
    tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
else
    # Fica esperando (pra Ctrl+C funcionar) sem imprimir log nenhum.
    wait
fi
