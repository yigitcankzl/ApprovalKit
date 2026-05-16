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
});

const result = await kit.gate("stripe-prod", "charge", {
  amount: 120,
  customer: "alice@example.com",
});
```

A decorator-style API mirroring the Python SDK is planned. Contributions
welcome — see [`sdk-ts/`](https://github.com/yigitcankzl/ApprovalKit/tree/main/sdk-ts) for the current scaffolding.
