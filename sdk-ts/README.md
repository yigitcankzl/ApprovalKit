# approvalkit-sdk

TypeScript/JavaScript SDK for [ApprovalKit](https://github.com/your-org/ApprovalKit) — human approval middleware for AI agents.

## Install

```bash
npm install approvalkit-sdk
# or
yarn add approvalkit-sdk
```

## Quick Start

```typescript
import { ApprovalKit, ApprovalDenied } from 'approvalkit-sdk';

const kit = new ApprovalKit({
  baseUrl: process.env.APPROVALKIT_BASE_URL,
  apiKey: process.env.APPROVALKIT_API_KEY,
  hmacSecret: process.env.APPROVALKIT_HMAC_SECRET,
  userId: 'my-ts-agent',
});

// Inline gate — blocks until approved or throws ApprovalDenied
try {
  const result = await kit.gate('gmail', 'send_email', {
    to: 'cto@company.com',
    subject: 'Q4 Budget Report',
    body: 'Please find the report attached.',
  });

  console.log('Approved!', result.finalParams);
  // finalParams may differ from original if approver modified them
} catch (err) {
  if (err instanceof ApprovalDenied) {
    console.log(`Denied: ${err.status}`);
    if (err.reason) {
      console.log(`Reason: ${err.reason}`); // Feature 4: denial feedback
    }
  }
}

// Decorator pattern
const safeDeploy = kit.requiresApproval('github', 'deploy')(
  async (params) => { /* fn body ignored — Token Vault executes */ }
);

const result = await safeDeploy({ env: 'production', branch: 'main' });
```

## Config

| Option | Env var | Default |
|--------|---------|---------|
| `baseUrl` | `APPROVALKIT_BASE_URL` | `http://localhost:8000` |
| `apiKey` | `APPROVALKIT_API_KEY` | `""` |
| `hmacSecret` | `APPROVALKIT_HMAC_SECRET` | `""` |
| `userId` | — | `"ts-agent"` |
| `pollInterval` | — | `3` (seconds) |
| `timeout` | — | `300` (seconds) |

## Features

- **`gate(connection, action, params)`** — submit approval request and wait
- **`requiresApproval(connection, action)(fn)`** — decorator for async functions
- **`checkStatus(jobId)`** — non-blocking status check
- **`listConnections()`** — list workspace connections
- **`ApprovalDenied`** — thrown on rejection/timeout/block, includes `reason` (Feature 4)
- Risk scores returned in `GateResult.riskScore` / `riskLevel` (Feature 7)

## Compatible Frameworks

- Node.js 18+ (native `fetch`)
- Vercel AI SDK
- LangChain.js
- Mastra
- Any TypeScript/JavaScript agent framework
