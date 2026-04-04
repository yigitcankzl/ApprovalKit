#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
# ApprovalKit — One-Command Setup
#
# This script sets up the entire ApprovalKit stack:
#   PostgreSQL, Redis, HashiCorp Vault, Ollama (LLM),
#   FastAPI backend, Celery worker, Next.js frontend
#
# Two modes:
#   ./setup.sh          → Uses pre-configured Auth0 tenant (demo)
#   ./setup.sh --custom → Prompts for your own Auth0 credentials
#
# Prerequisites:
#   - Docker & Docker Compose V2
#   - ~10GB disk (Ollama model + Docker images)
#   - NVIDIA GPU recommended (CPU fallback available)
# ─────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

log()  { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }
step() { echo -e "\n${CYAN}${BOLD}[$1]${NC} $2"; }

echo ""
echo -e "${BOLD}"
echo "   █████╗ ██████╗ ██████╗ ██████╗  ██████╗ ██╗   ██╗ █████╗ ██╗     "
echo "  ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██║   ██║██╔══██╗██║     "
echo "  ███████║██████╔╝██████╔╝██████╔╝██║   ██║██║   ██║███████║██║     "
echo "  ██╔══██║██╔═══╝ ██╔═══╝ ██╔══██╗██║   ██║╚██╗ ██╔╝██╔══██║██║     "
echo "  ██║  ██║██║     ██║     ██║  ██║╚██████╔╝ ╚████╔╝ ██║  ██║███████╗"
echo "  ╚═╝  ╚═╝╚═╝     ╚═╝     ╚═╝  ╚═╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "  ${DIM}Human Approval Middleware for AI Agents${NC}"
echo -e "  ${DIM}Built with Auth0 Token Vault + CIBA + FGA${NC}"
echo ""

# ── 1. Prerequisites ────────────────────────────────────────

step "1/7" "Checking prerequisites"

MISSING=0
for cmd in docker curl; do
    if command -v $cmd &>/dev/null; then
        log "$cmd found"
    else
        err "$cmd not installed"
        MISSING=1
    fi
done

if ! docker compose version &>/dev/null; then
    err "Docker Compose V2 not found"
    MISSING=1
else
    log "Docker Compose V2 found"
fi

if ! docker info &>/dev/null 2>&1; then
    err "Docker daemon not running — start Docker first"
    MISSING=1
else
    log "Docker daemon running"
fi

[ $MISSING -eq 1 ] && echo -e "\n  ${RED}Fix the above issues and re-run ./setup.sh${NC}" && exit 1

# ── 2. Environment Configuration ────────────────────────────

step "2/7" "Configuring environment"

# Check if .env exists with real Auth0 credentials
if [ -f .env ] && grep -q "AUTH0_DOMAIN=" .env 2>/dev/null && ! grep -q "AUTH0_DOMAIN=your-" .env 2>/dev/null; then
    log ".env exists with Auth0 credentials"
elif [ -f .env.example ]; then
    cp .env.example .env
    # Generate HMAC_SECRET automatically
    HMAC=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    sed -i "s/HMAC_SECRET=generate-a-random-64-char-hex-string/HMAC_SECRET=${HMAC}/" .env
    warn ".env created from example — edit Auth0 credentials before use"
else
    err "No .env or .env.example found"
    exit 1
fi

# Auto-generate frontend/.env.local from backend .env values
_sync_frontend_env() {
    local AUTH0_DOMAIN AUTH0_WEB_CLIENT_ID AUTH0_WEB_CLIENT_SECRET AUTH0_SECRET
    AUTH0_DOMAIN=$(grep "^AUTH0_DOMAIN=" .env 2>/dev/null | cut -d= -f2-)
    AUTH0_WEB_CLIENT_ID=$(grep "^AUTH0_WEB_CLIENT_ID=" .env 2>/dev/null | cut -d= -f2-)
    AUTH0_WEB_CLIENT_SECRET=$(grep "^AUTH0_WEB_CLIENT_SECRET=" .env 2>/dev/null | cut -d= -f2-)
    AUTH0_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)

    cat > frontend/.env.local <<ENVEOF
NEXT_PUBLIC_API_URL=http://localhost:8000
AUTH0_SECRET=${AUTH0_SECRET}
AUTH0_BASE_URL=http://localhost:3000
AUTH0_DOMAIN=${AUTH0_DOMAIN}
AUTH0_CLIENT_ID=${AUTH0_WEB_CLIENT_ID}
AUTH0_CLIENT_SECRET=${AUTH0_WEB_CLIENT_SECRET}
APP_BASE_URL=http://localhost:3000
ENVEOF
}

if [ -f frontend/.env.local ]; then
    # Check if it still has placeholder values
    if grep -q "AUTH0_DOMAIN=your-" frontend/.env.local 2>/dev/null || grep -q "AUTH0_CLIENT_ID=your-" frontend/.env.local 2>/dev/null; then
        _sync_frontend_env
        log "frontend/.env.local synced from .env (replaced placeholders)"
    else
        log "frontend/.env.local exists"
    fi
else
    _sync_frontend_env
    log "frontend/.env.local generated from .env"
fi

# ── 3. GPU Detection ────────────────────────────────────────

step "3/7" "Detecting hardware"

if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    log "NVIDIA GPU: $GPU_NAME"

    if dpkg -l nvidia-container-toolkit &>/dev/null 2>&1; then
        log "NVIDIA Container Toolkit installed"
    else
        warn "NVIDIA Container Toolkit not installed"
        echo -e "    ${DIM}Ollama will use CPU. For GPU support, run:${NC}"
        echo -e "    ${DIM}curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg${NC}"
        echo -e "    ${DIM}sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit${NC}"
        echo -e "    ${DIM}sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker${NC}"
    fi
else
    warn "No NVIDIA GPU detected — Ollama will run on CPU (slower but functional)"
fi

# ── 4. Build & Start Services ────────────────────────────────

step "4/7" "Starting services (this may take a few minutes on first run)"

docker compose up -d --build 2>&1 | while read line; do
    case "$line" in
        *"Created"*|*"Started"*) log "$line" ;;
        *"Error"*|*"error"*)     err "$line" ;;
        *"Built"*)               info "$line" ;;
    esac
done

echo ""
info "Waiting for services to become healthy..."

# Wait for PostgreSQL
printf "  Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U approvalkit -d approvalkit &>/dev/null 2>&1; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    printf "."
    [ $i -eq 30 ] && echo -e " ${RED}FAILED${NC}" && err "PostgreSQL did not start" && exit 1
    sleep 2
done

# Wait for Redis
printf "  Waiting for Redis..."
for i in $(seq 1 15); do
    if docker compose exec -T redis redis-cli ping &>/dev/null 2>&1; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    printf "."
    [ $i -eq 15 ] && echo -e " ${RED}FAILED${NC}"
    sleep 2
done

# Wait for API
printf "  Waiting for API..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    printf "."
    [ $i -eq 30 ] && echo -e " ${RED}FAILED${NC}" && err "API did not start — check: docker compose logs api"
    sleep 3
done

# Wait for Frontend
printf "  Waiting for Frontend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:3000 &>/dev/null; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    printf "."
    [ $i -eq 30 ] && echo -e " ${YELLOW}slow${NC}"
    sleep 3
done

# ── 5. Pull LLM Model ───────────────────────────────────────

step "5/7" "Setting up AI model (Qwen 2.5 7B)"

printf "  Waiting for Ollama..."
for i in $(seq 1 20); do
    if docker compose exec -T ollama ollama list &>/dev/null 2>&1; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    printf "."
    [ $i -eq 20 ] && echo -e " ${YELLOW}slow — may need more time${NC}"
    sleep 3
done

if docker compose exec -T ollama ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
    log "Qwen 2.5 7B model already downloaded"
else
    echo ""
    echo -e "  ${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${YELLOW}║  Downloading Qwen 2.5 7B model (4.7 GB)                 ║${NC}"
    echo -e "  ${YELLOW}║  This is a ONE-TIME download.                            ║${NC}"
    echo -e "  ${YELLOW}║  Estimated time: 5-30 min depending on internet speed.   ║${NC}"
    echo -e "  ${YELLOW}║  You can skip this and use Groq (free API key) instead.  ║${NC}"
    echo -e "  ${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    docker compose exec -T ollama ollama pull qwen2.5:7b 2>&1 | tail -1
    log "Model downloaded"
fi

# ── 6. Seed Demo Data ───────────────────────────────────────

step "6/7" "Preparing demo environment"

# Find workspace owner
USER_SUB=$(docker compose exec -T api python3 -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from api.config import get_settings
from api.models.workspace import Workspace
s = get_settings()
async def g():
    e = create_async_engine(s.DATABASE_URL)
    sm = sessionmaker(e, class_=AsyncSession, expire_on_commit=False)
    async with sm() as db:
        ws = (await db.execute(select(Workspace))).scalars().first()
        if ws and ws.owner_auth0_sub: print(ws.owner_auth0_sub)
    await e.dispose()
asyncio.run(g())
" 2>/dev/null || echo "")

if [ -n "$USER_SUB" ]; then
    # Seed demo rules, connections, approvers
    SEED=$(curl -sf -X POST "http://localhost:8000/api/v1/demo/seed?real_user_id=$USER_SUB" \
        -H "X-User-Sub: $USER_SUB" 2>/dev/null || echo "")
    if [ -n "$SEED" ]; then
        log "Demo rules, connections, and approvers created"
    else
        warn "Demo seed may have partially succeeded (rules might already exist)"
    fi

    # Configure Ollama as AI provider
    curl -sf -X POST "http://localhost:8000/api/v1/workspace/ai-key" \
        -H "Content-Type: application/json" \
        -H "X-User-Sub: $USER_SUB" \
        -d '{"api_key":"ollama:ollama","provider":"ollama"}' &>/dev/null && \
        log "Ollama configured as AI provider" || \
        warn "AI provider config skipped — configure in app"
else
    warn "No workspace found yet — log in at http://localhost:3000 first"
    warn "After login, complete the Setup Wizard, then re-run: ./setup.sh"
fi

# ── 7. Summary ──────────────────────────────────────────────

step "7/7" "Setup complete!"

echo ""
echo -e "  ${BOLD}Services:${NC}"
docker compose ps --format "    {{.Name}}: {{.Status}}" 2>/dev/null
echo ""

echo -e "  ${BOLD}Access:${NC}"
echo -e "    ${GREEN}App:${NC}        http://localhost:3000"
echo -e "    ${GREEN}API:${NC}        http://localhost:8000"
echo -e "    ${GREEN}API Docs:${NC}   http://localhost:8000/docs"
echo ""

echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "    1. Open ${CYAN}http://localhost:3000${NC}"
echo -e "    2. Log in with Auth0 (or create an account)"
echo -e "    3. Complete the Setup Wizard (saves your API key)"
echo -e "    4. Go to ${CYAN}Demos${NC} → pick any agent → try a scenario"
echo ""

echo -e "  ${BOLD}What happens:${NC}"
echo -e "    - AI agent (powered by local Qwen 2.5 LLM) reasons about your request"
echo -e "    - Agent calls tools: Stripe charges, Gmail emails, Slack messages"
echo -e "    - ApprovalKit evaluates rules: auto-approve, pending, or blocked"
echo -e "    - You approve/reject in real-time from the split-screen dashboard"
echo -e "    - On approval, Auth0 Token Vault executes — agent never sees credentials"
echo ""

echo -e "  ${BOLD}Demo Agents (10):${NC}"
echo -e "    ${DIM}E-Commerce, Finance, DevOps, Security, HR, GDPR,${NC}"
echo -e "    ${DIM}Open Source, Research, Communications, and more${NC}"
echo ""

echo -e "  ${BOLD}Commands:${NC}"
echo -e "    ${DIM}Stop:${NC}    docker compose down"
echo -e "    ${DIM}Logs:${NC}    docker compose logs -f api"
echo -e "    ${DIM}Reset:${NC}   docker compose down -v && ./setup.sh"
echo ""

echo -e "  ${BOLD}Auth0 Integration:${NC}"
echo -e "    This demo uses Auth0 Token Vault for secure credential management."
echo -e "    OAuth connections (Stripe, Gmail, Slack, GitHub) are configured via"
echo -e "    the Connections page after login. Agents never see API credentials —"
echo -e "    everything is mediated through Auth0 Token Exchange (RFC 8693)."
echo ""
echo -e "    ${DIM}To use your own Auth0 tenant, update .env and frontend/.env.local${NC}"
echo -e "    ${DIM}with your Auth0 domain, client IDs, and secrets.${NC}"
echo ""
