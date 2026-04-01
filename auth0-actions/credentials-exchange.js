/**
 * Auth0 Action — Credentials Exchange: Audit Token Vault Usage
 * ==============================================================
 *
 * This Action runs during the client-credentials flow (M2M token exchange).
 * It sends an audit event to ApprovalKit whenever a Token Vault exchange
 * occurs, creating a complete chain of custody:
 *
 *   Agent Request → Rule Match → CIBA Approval → Token Exchange (this Action) → Execution
 *
 * Setup:
 *   1. Go to Auth0 Dashboard > Actions > Flows > Machine to Machine
 *   2. Create a new custom Action with this code
 *   3. Add secrets:
 *      - APPROVALKIT_API_URL
 *      - APPROVALKIT_WEBHOOK_SECRET
 *   4. Deploy and drag into the M2M flow
 */

const crypto = require('crypto');

exports.onExecuteCredentialsExchange = async (event, api) => {
  const apiUrl = event.secrets.APPROVALKIT_API_URL;
  const webhookSecret = event.secrets.APPROVALKIT_WEBHOOK_SECRET;

  if (!apiUrl || !webhookSecret) return;

  const payload = JSON.stringify({
    event_type: 'token_exchange_audit',
    client_id: event.client?.client_id || 'unknown',
    client_name: event.client?.name || 'unknown',
    audience: event.resource_server?.identifier || 'unknown',
    scopes: event.request?.body?.scope || '',
    timestamp: new Date().toISOString(),
    ip: event.request?.ip || 'unknown',
  });

  const signature = crypto
    .createHmac('sha256', webhookSecret)
    .update(payload)
    .digest('hex');

  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(`${apiUrl}/api/v1/auth0-webhook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Auth0-Signature': signature,
          'X-Auth0-Action': 'credentials-exchange',
        },
        body: payload,
        signal: AbortSignal.timeout(attempt === 0 ? 3000 : 5000),
      });

      if (response.ok) return;
      if (response.status === 429) continue; // Retry rate-limited requests
      if (response.status >= 400 && response.status < 500) break; // Don't retry other client errors
    } catch (error) {
      if (attempt === maxRetries) {
        console.log(`ApprovalKit audit failed after ${maxRetries + 1} attempts: ${error.message}`);
      }
    }
  }
};
