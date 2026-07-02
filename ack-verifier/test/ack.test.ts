/**
 * End-to-end ACK-ID round-trip: mint real did:key identities + a real
 * owner-issued ControllerCredential, sign a presentation, and verify it —
 * exercising Catena's actual @agentcommercekit packages. Then prove the
 * negative paths (untrusted owner, wrong audience, impersonation, expiry).
 */
import { describe, it, expect, beforeAll } from "vitest"
import {
  generateIdentity,
  issueControllerCredential,
  createPresentation,
  verifyPresentation,
  type AgentIdentity,
} from "../src/index.js"

const AUDIENCE = "did:web:approvalkit.example"

let owner: AgentIdentity
let agent: AgentIdentity
let credentialJwt: string

beforeAll(async () => {
  owner = await generateIdentity()
  agent = await generateIdentity()
  credentialJwt = await issueControllerCredential(owner, agent.did)
})

describe("verifyPresentation", () => {
  it("accepts a well-formed presentation from a trusted owner", async () => {
    const presentation = await createPresentation(agent, credentialJwt, {
      audience: AUDIENCE,
      nonce: "n-1",
    })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: [owner.did],
      nonce: "n-1",
    })
    expect(result.verified).toBe(true)
    expect(result.agentDid).toBe(agent.did)
    expect(result.ownerDid).toBe(owner.did)
  })

  it("rejects a credential from an untrusted owner", async () => {
    const presentation = await createPresentation(agent, credentialJwt, { audience: AUDIENCE })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: ["did:key:zSomeoneElse"],
    })
    expect(result.verified).toBe(false)
    expect(result.reason).toMatch(/credential/i)
  })

  it("rejects a presentation minted for a different audience", async () => {
    const presentation = await createPresentation(agent, credentialJwt, {
      audience: "did:web:somewhere-else",
    })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: [owner.did],
    })
    expect(result.verified).toBe(false)
    expect(result.reason).toMatch(/envelope/i)
  })

  it("rejects impersonation: a different key presenting someone else's credential", async () => {
    // Attacker controls its own DID but replays the real agent's credential.
    const attacker = await generateIdentity()
    const presentation = await createPresentation(attacker, credentialJwt, { audience: AUDIENCE })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: [owner.did],
    })
    expect(result.verified).toBe(false)
    expect(result.reason).toMatch(/not the presenting agent/i)
  })

  it("enforces nonce when supplied", async () => {
    const presentation = await createPresentation(agent, credentialJwt, {
      audience: AUDIENCE,
      nonce: "real-nonce",
    })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: [owner.did],
      nonce: "expected-different",
    })
    expect(result.verified).toBe(false)
    expect(result.reason).toMatch(/nonce/i)
  })

  it("rejects an expired presentation", async () => {
    const presentation = await createPresentation(agent, credentialJwt, {
      audience: AUDIENCE,
      expiresIn: -3600, // expired an hour ago — well beyond did-jwt's 300s skew
    })
    const result = await verifyPresentation({
      presentation,
      expectedAudience: AUDIENCE,
      trustedIssuers: [owner.did],
    })
    expect(result.verified).toBe(false)
  })

  it("rejects garbage input without throwing", async () => {
    const result = await verifyPresentation({ presentation: "not-a-jwt" })
    expect(result.verified).toBe(false)
  })
})
