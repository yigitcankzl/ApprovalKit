/**
 * ACK-ID presentation verification.
 *
 * Two cryptographic checks, in order:
 *  1. Envelope — verify the presentation JWT's signature against its `iss`
 *     DID. This proves the *caller* controls the agent DID (not just that it
 *     replayed a credential). Also enforces `aud` and `exp`.
 *  2. Credential — parse + verify the embedded ControllerCredential: a valid
 *     proof from a TRUSTED owner (issuer), not expired/revoked, of type
 *     ControllerCredential, naming the presenting agent as its subject.
 *
 * Note on the ownership model: a trusted owner cryptographically signing
 * "this agent is mine" (issuer ∈ trustedIssuers, subject == agent) is a
 * complete ownership proof. ACK also ships `getControllerClaimVerifier()`,
 * which additionally cross-checks that the agent's *DID document* declares
 * the owner as its `controller` — bidirectional, but it requires the agent
 * to publish a resolvable did:web document. We keep that as optional
 * hardening (see ENABLE_CONTROLLER_DOC_CHECK) so did:key agents work without
 * hosting; turn it on once agents publish did:web docs.
 *
 * Returns `{verified:false, reason}` for any credential problem (never throws
 * for bad input); throws only on unexpected internal errors.
 */
import { getDidResolver } from "@agentcommercekit/did"
import { verifyJwt } from "@agentcommercekit/jwt"
import { parseJwtCredential, verifyParsedCredential } from "@agentcommercekit/vc"
import { getControllerClaimVerifier, isControllerCredential } from "@agentcommercekit/ack-id"

// Opt-in bidirectional check (requires did:web agent documents with a
// `controller` field). Off by default so did:key agents verify out of the box.
const ENABLE_CONTROLLER_DOC_CHECK = process.env.ACK_CONTROLLER_DOC_CHECK === "1"

export interface VerifyInput {
  presentation: string
  expectedAudience?: string | null
  trustedIssuers?: string[] | null
  nonce?: string | null
}

export interface VerifyResult {
  verified: boolean
  agentDid?: string
  ownerDid?: string
  reason?: string
}

function issuerId(issuer: unknown): string {
  if (typeof issuer === "string") return issuer
  if (issuer && typeof issuer === "object" && "id" in issuer) {
    return String((issuer as { id: unknown }).id)
  }
  return String(issuer)
}

function subjectId(subject: unknown): string {
  const s = Array.isArray(subject) ? subject[0] : subject
  return String((s as { id?: unknown } | undefined)?.id)
}

export async function verifyPresentation(input: VerifyInput): Promise<VerifyResult> {
  if (!input?.presentation || typeof input.presentation !== "string") {
    return { verified: false, reason: "missing presentation" }
  }
  const resolver = getDidResolver()

  // 1) Envelope: agent's signature over aud/nonce/exp + embedded vc.
  let payload: Record<string, unknown>
  let agentDid: string
  try {
    const verified = await verifyJwt(input.presentation, {
      resolver,
      audience: input.expectedAudience ?? undefined,
    })
    payload = verified.payload as Record<string, unknown>
    agentDid = verified.issuer
  } catch (err) {
    return { verified: false, reason: `envelope verification failed: ${(err as Error).message}` }
  }

  if (input.nonce && payload.nonce !== input.nonce) {
    return { verified: false, reason: "nonce mismatch" }
  }

  const credentialJwt = payload.vc
  if (!credentialJwt || typeof credentialJwt !== "string") {
    return { verified: false, reason: "presentation carries no controller credential (vc)" }
  }

  // 2) Credential: owner-issued, trusted, subject == the presenting agent.
  const trustedIssuers = input.trustedIssuers?.length ? input.trustedIssuers : undefined
  try {
    const credential = await parseJwtCredential(credentialJwt, resolver)

    if (!isControllerCredential(credential)) {
      return { verified: false, reason: "embedded credential is not a ControllerCredential" }
    }

    // Throws on bad proof / expiry / revocation / untrusted issuer.
    await verifyParsedCredential(credential, {
      resolver,
      trustedIssuers,
      verifiers: ENABLE_CONTROLLER_DOC_CHECK ? [getControllerClaimVerifier()] : [],
    })

    const subject = subjectId(credential.credentialSubject)
    if (subject !== agentDid) {
      return {
        verified: false,
        reason: `credential subject (${subject}) is not the presenting agent (${agentDid})`,
      }
    }

    return { verified: true, agentDid, ownerDid: issuerId(credential.issuer) }
  } catch (err) {
    return { verified: false, reason: `credential verification failed: ${(err as Error).message}` }
  }
}
