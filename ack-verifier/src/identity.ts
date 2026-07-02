/**
 * ACK-ID minting helpers (agent-side).
 *
 * Thin wrappers over Catena's Agent Commerce Kit packages for the three
 * things an agent / its owner need to do:
 *   1. generate a did:key identity (keypair + DID)
 *   2. (owner) issue a ControllerCredential to an agent
 *   3. (agent) mint a short-lived presentation JWT for a verifier
 *
 * The matching verification lives in ./verify.ts.
 */
import { generateKeypair, keypairToJwk, jwkToKeypair, type Keypair } from "@agentcommercekit/keys"
import { createDidKeyUri, type DidUri } from "@agentcommercekit/did"
import { createControllerCredential } from "@agentcommercekit/ack-id"
import { createJwt, createJwtSigner, curveToJwtAlgorithm, type JwtAlgorithm } from "@agentcommercekit/jwt"

export interface AgentIdentity {
  did: DidUri
  keypair: Keypair
  alg: JwtAlgorithm
}

/** Generate a fresh did:key identity (secp256k1 — best did-jwt support). */
export async function generateIdentity(): Promise<AgentIdentity> {
  const keypair = await generateKeypair("secp256k1")
  const did = createDidKeyUri(keypair)
  return { did, keypair, alg: curveToJwtAlgorithm(keypair.curve) }
}

/** Serialized form for persisting an identity (includes the PRIVATE key). */
export interface SerializedIdentity {
  did: DidUri
  alg: JwtAlgorithm
  jwk: unknown
}

export function exportIdentity(identity: AgentIdentity): SerializedIdentity {
  return { did: identity.did, alg: identity.alg, jwk: keypairToJwk(identity.keypair) }
}

export function importIdentity(serialized: SerializedIdentity): AgentIdentity {
  return {
    did: serialized.did,
    alg: serialized.alg,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    keypair: jwkToKeypair(serialized.jwk as any),
  }
}

/**
 * Owner issues a ControllerCredential to an agent, signed as a JWT VC.
 * This is the cryptographic "I, the legal entity, authorize this agent".
 */
export async function issueControllerCredential(
  owner: AgentIdentity,
  agentDid: DidUri,
  { expiresIn = 60 * 60 * 24 * 365 }: { expiresIn?: number } = {},
): Promise<string> {
  const credential = createControllerCredential({
    subject: agentDid,
    controller: owner.did,
    issuer: owner.did,
  })
  return await createJwt(
    { vc: credential, sub: agentDid },
    { issuer: owner.did, signer: createJwtSigner(owner.keypair), expiresIn },
    { alg: owner.alg },
  )
}

/**
 * Agent mints a presentation: a short-lived JWT it signs with its OWN key
 * (proving control of its DID) that carries the owner-issued credential.
 * `audience` should be the verifier's DID so the token can't be replayed
 * against a different verifier.
 */
export async function createPresentation(
  agent: AgentIdentity,
  credentialJwt: string,
  {
    audience,
    nonce,
    expiresIn = 5 * 60,
  }: { audience?: string | null; nonce?: string | null; expiresIn?: number },
): Promise<string> {
  return await createJwt(
    { vc: credentialJwt, nonce: nonce ?? undefined, aud: audience ?? undefined },
    { issuer: agent.did, signer: createJwtSigner(agent.keypair), expiresIn },
    { alg: agent.alg },
  )
}
