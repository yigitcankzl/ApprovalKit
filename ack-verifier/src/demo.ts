/**
 * One-command ACK-ID demo — no server, no DB, no Auth0.
 *
 *   npm install && npm run demo
 *
 * Shows the full Agent Commerce Kit identity loop that ApprovalKit gates on:
 * an owner issues a ControllerCredential, the agent presents it, and the
 * verifier checks it. Then two negative cases prove it actually rejects.
 */
import { generateIdentity, issueControllerCredential, createPresentation } from "./identity.js"
import { verifyPresentation } from "./verify.js"

const log = (s = "") => console.log(s)

async function main() {
  log("ACK-ID demo — built on Catena's Agent Commerce Kit\n")

  // 1. identities (owner = legal entity, agent = the AI, verifier = the gate)
  const owner = await generateIdentity()
  const agent = await generateIdentity()
  const verifier = await generateIdentity() // only its DID is used, as the audience
  log(`owner     ${owner.did}`)
  log(`agent     ${agent.did}`)
  log(`verifier  ${verifier.did}\n`)

  // 2. owner cryptographically authorizes the agent
  const credential = await issueControllerCredential(owner, agent.did)
  log("→ owner issued a ControllerCredential to the agent (signed JWT VC)")

  // 3. agent mints a presentation, signed with its OWN key, bound to this
  //    verifier (aud) and a nonce so it can't be replayed
  const nonce = "demo-nonce"
  const presentation = await createPresentation(agent, credential, { audience: verifier.did, nonce })
  log("→ agent minted a presentation (aud = verifier, nonce bound)\n")

  // 4a. happy path — owner is trusted, agent controls the DID, audience matches
  const ok = await verifyPresentation({
    presentation,
    expectedAudience: verifier.did,
    trustedIssuers: [owner.did],
    nonce,
  })
  log(`verify (owner trusted)    → ${JSON.stringify(ok)}`)

  // 4b. same presentation, but the owner is NOT in the trusted set → must fail
  const untrusted = await verifyPresentation({
    presentation,
    expectedAudience: verifier.did,
    trustedIssuers: ["did:key:z6MkuntrustedOwnerDidThatWeDoNotTrust000000000000"],
    nonce,
  })
  log(`verify (owner untrusted)  → ${JSON.stringify(untrusted)}`)

  // 4c. token was minted for the verifier, replayed against a different aud → must fail
  const wrongAudience = await verifyPresentation({
    presentation,
    expectedAudience: agent.did,
    trustedIssuers: [owner.did],
    nonce,
  })
  log(`verify (wrong audience)   → ${JSON.stringify(wrongAudience)}`)

  log("\nverified=true only when the owner is trusted AND the agent controls its DID AND the audience matches.")
  log("In ApprovalKit this runs before the human-approval gate on a high-stakes action (e.g. a payment).")

  if (!ok.verified || untrusted.verified || wrongAudience.verified) {
    console.error("\nDEMO FAILED: unexpected verification result")
    process.exit(1)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
