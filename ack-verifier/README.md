# @approvalkit/ack-verifier

An **ACK-ID agent-identity verifier** built on [Catena's Agent Commerce Kit](https://www.agentcommercekit.com/). It's the identity layer ApprovalKit checks before it runs a human-approval gate on a high-stakes action (a payment, a deploy): confirm *which* agent is calling and *who* owns it, then decide.

It's both a small library and an HTTP sidecar. ApprovalKit's Python `AckIdAgentVerifier` POSTs presentations to it; you can also use it standalone.

## Try it (one command)

```bash
npm install && npm run demo
```

The demo runs the full loop with no server, DB, or Auth0:

```
owner issues a ControllerCredential  ->  agent presents it  ->  verifier checks it
```

and prints the happy path plus two rejections (untrusted owner, replayed audience), so you can see it actually fails closed:

```
verify (owner trusted)    -> {"verified":true, "agentDid":"did:key:…", "ownerDid":"did:key:…"}
verify (owner untrusted)  -> {"verified":false,"reason":"credential verification failed: Issuer is not trusted …"}
verify (wrong audience)   -> {"verified":false,"reason":"envelope verification failed: JWT audience does not match …"}
```

## What it verifies

A presentation is a short-lived JWT the agent signs with its own key, carrying an owner-issued `ControllerCredential`. `verifyPresentation` does two cryptographic checks, fail-closed:

1. **Envelope** — the presentation JWT's signature resolves to its `iss` DID (proves the caller controls the agent DID, not just replays a credential), and `aud` / `exp` hold.
2. **Credential** — the embedded `ControllerCredential` has a valid proof from a **trusted** owner (issuer), isn't expired/revoked, is of type `ControllerCredential`, and names the presenting agent as its subject.

Optional bidirectional hardening (`ACK_CONTROLLER_DOC_CHECK=1`) also cross-checks the agent's did:web document declares the owner as `controller`; off by default so did:key agents work without hosting.

## As a sidecar

```bash
npm start   # ack-verifier listening on :8788
```

```
POST /verify  { presentation, expectedAudience?, trustedIssuers?, nonce? }
              -> 200 { verified, agentDid?, ownerDid?, reason? }
GET  /health  -> 200 { status: "ok" }
```

Wire it into the full ApprovalKit stack with the ACK overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.ack.yml up
```

Built on `@agentcommercekit/{ack-id,did,jwt,keys,vc}`.
