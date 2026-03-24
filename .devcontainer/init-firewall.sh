#!/usr/bin/env bash
# -------------------------------------------------------------------
# init-firewall.sh
# Outbound firewall: only allow traffic to whitelisted domains.
# Based on the approach used in Anthropic's official devcontainer.
# -------------------------------------------------------------------
set -euo pipefail

# ---------- whitelisted domains ----------
ALLOWED_DOMAINS=(
  # Claude API
  api.anthropic.com
  auth.anthropic.com
  console.anthropic.com
  statsig.anthropic.com
  # npm registry
  registry.npmjs.org
  # GitHub
  github.com
  api.github.com
  # PyPI
  pypi.org
  files.pythonhosted.org
)

# ---------- flush existing rules ----------
iptables -F OUTPUT 2>/dev/null || true
iptables -F INPUT  2>/dev/null || true

# ---------- default policies ----------
iptables -P INPUT   ACCEPT
iptables -P FORWARD DROP
iptables -P OUTPUT  DROP

# ---------- loopback ----------
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A INPUT  -i lo -j ACCEPT

# ---------- established / related ----------
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT  -m state --state ESTABLISHED,RELATED -j ACCEPT

# ---------- DNS (udp+tcp 53) ----------
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# ---------- resolve & allow whitelisted domains ----------
for domain in "${ALLOWED_DOMAINS[@]}"; do
  # Resolve all A records for the domain
  ips=$(dig +short A "$domain" 2>/dev/null | grep -E '^[0-9]+\.' || true)
  for ip in $ips; do
    iptables -A OUTPUT -d "$ip" -p tcp --dport 443 -j ACCEPT
    iptables -A OUTPUT -d "$ip" -p tcp --dport 80  -j ACCEPT
  done
done

# ---------- log dropped packets (optional, useful for debugging) ----------
iptables -A OUTPUT -j LOG --log-prefix "DEVCONTAINER-BLOCKED: " --log-level 4 2>/dev/null || true

echo "[init-firewall] Firewall configured. Allowed domains:"
printf "  - %s\n" "${ALLOWED_DOMAINS[@]}"
