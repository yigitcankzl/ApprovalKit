FROM node:20-bookworm-slim

# System dependencies: dev tools + firewall utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl sudo ca-certificates ripgrep fd-find jq python3 python3-pip \
    iptables ipset iproute2 dnsutils \
  && rm -rf /var/lib/apt/lists/*

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code

# Allow the node user to run commands via sudo without password
RUN echo "node ALL=(ALL) NOPASSWD: ALL" \
    >> /etc/sudoers.d/node-nopasswd \
  && chmod 0440 /etc/sudoers.d/node-nopasswd

# Copy firewall script into the image
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Ensure the claude config dir exists with correct ownership
RUN mkdir -p /home/node/.claude && chown node:node /home/node/.claude

USER node
WORKDIR /workspace
