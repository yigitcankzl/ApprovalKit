/**
 * Auth0 Action — Post-Login: Sync User Role to ApprovalKit FGA
 * ==============================================================
 *
 * This Action runs after every successful login. It reads the user's
 * ApprovalKit role from app_metadata and writes the corresponding FGA
 * tuple so that the dashboard enforces fine-grained authorization
 * without any manual provisioning.
 *
 * Setup:
 *   1. Go to Auth0 Dashboard > Actions > Flows > Login
 *   2. Create a new custom Action with this code
 *   3. Add secrets:
 *      - APPROVALKIT_API_URL  (e.g. https://your-api.example.com)
 *      - APPROVALKIT_WEBHOOK_SECRET  (shared secret for HMAC verification)
 *   4. Deploy and drag into the Login flow
 *
 * User metadata expected:
 *   user.app_metadata.approvalkit_role = "admin" | "approver" | "viewer" | "agent_owner"
 *   user.app_metadata.approvalkit_workspace = "<workspace-id>"
 */

const crypto = require('crypto');

exports.onExecutePostLogin = async (event, api) => {
  const role = event.user.app_metadata?.approvalkit_role;
  const workspaceId = event.user.app_metadata?.approvalkit_workspace;

  // Skip if user has no ApprovalKit config
  if (!role || !workspaceId) return;

  const apiUrl = event.secrets.APPROVALKIT_API_URL;
  const webhookSecret = event.secrets.APPROVALKIT_WEBHOOK_SECRET;

  if (!apiUrl || !webhookSecret) {
    console.log('ApprovalKit: Missing API URL or webhook secret — skipping FGA sync');
    return;
  }

  const payload = JSON.stringify({
    event_type: 'post_login_fga_sync',
    user_id: event.user.user_id,
    email: event.user.email,
    role: role,
    workspace_id: workspaceId,
    timestamp: new Date().toISOString(),
    connection: event.connection?.name || 'unknown',
    ip: event.request?.ip || 'unknown',
  });

  // HMAC-SHA256 signature for webhook verification
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
        'X-Auth0-Action': 'post-login',
      },
      body: payload,
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      console.log(`ApprovalKit FGA sync failed: HTTP ${response.status}`);
    }
  } catch (error) {
    // Non-blocking — login continues even if FGA sync fails
    console.log(`ApprovalKit FGA sync error: ${error.message}`);
  }

  // Add role to ID token custom claim for frontend visibility
  api.idToken.setCustomClaim('https://approvalkit.dev/role', role);
  api.idToken.setCustomClaim('https://approvalkit.dev/workspace', workspaceId);
};
