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

  try {
    const response = await fetch(`${apiUrl}/api/v1/auth0-webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Auth0-Signature': signature,
        'X-Auth0-Action': 'credentials-exchange',
      },
      body: payload,
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      console.log(`ApprovalKit audit failed: HTTP ${response.status}`);
    }
  } catch (error) {
    // Non-blocking — token exchange continues
    console.log(`ApprovalKit audit error: ${error.message}`);
  }
};
