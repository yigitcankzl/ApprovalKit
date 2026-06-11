# TypeScript SDK reference

> ⚠️ The TypeScript SDK is currently a thin port and is not yet
> published to npm. The reference below describes the intended API;
> implementation tracking lives in
> [#TODO](https://github.com/yigitcankzl/ApprovalKit/issues).

## Install (planned)

```bash
npm install approvalkit-sdk
# or
pnpm add approvalkit-sdk
```

## Usage

```ts
import { ApprovalKit, ApprovalDenied } from "approvalkit-sdk";

const kit = new ApprovalKit({
  baseUrl: "http://localhost:8000",
  apiKey: process.env.APPROVALKIT_API_KEY!,
  hmacSecret: process.env.APPROVALKIT_HMAC_SECRET!,
  userId: "my-agent",
  executionMode: "client", // "client" (default) | "server"
});

// gate() returns the approval result only — you run the action (client mode)
const result = await kit.gate("stripe-prod", "charge", {
  amount: 120,
  customer: "alice@example.com",
});
if (result.status === "approved") {
  await stripe.charges.create(result.finalParams);
}
```

## Execution modes

- **`client`** (default): after a human approves, `requiresApproval` runs **your
  function** with the approved (possibly modified) params and returns its value.
- **`server`**: legacy — your function is never called; ApprovalKit executes the
  action server-side (Auth0 Token Vault) and the wrapper resolves to the result.

```ts
// client mode: your function runs with finalParams after approval
const safeSend = kit.requiresApproval("gmail", "send_email")(sendEmail);
const sent = await safeSend({ to: "cto@co.com", subject: "Q4" });
```

Set it via `executionMode` or the `APPROVALKIT_EXECUTION_MODE` env var.

See [`sdk-ts/`](https://github.com/yigitcankzl/ApprovalKit/tree/main/sdk-ts) for the source.
