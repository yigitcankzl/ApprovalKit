/**
 * ack-verifier HTTP service.
 *
 * One endpoint, no framework (node:http) — this is a verification sidecar,
 * not an app. ApprovalKit's Python `AckIdAgentVerifier` POSTs here.
 *
 *   POST /verify  { presentation, expectedAudience?, trustedIssuers?, nonce? }
 *                 -> 200 { verified, agentDid?, ownerDid?, reason? }
 *   GET  /health  -> 200 { status: "ok" }
 */
import { createServer } from "node:http"
import { verifyPresentation, type VerifyInput } from "./verify.js"

const PORT = Number(process.env.PORT ?? 8788)
const MAX_BODY = 64 * 1024 // presentations are small JWTs; cap to avoid abuse

const server = createServer(async (req, res) => {
  const json = (status: number, body: unknown) => {
    res.writeHead(status, { "content-type": "application/json" })
    res.end(JSON.stringify(body))
  }

  if (req.method === "GET" && req.url === "/health") {
    return json(200, { status: "ok" })
  }

  if (req.method === "POST" && req.url === "/verify") {
    let body = ""
    let tooBig = false
    for await (const chunk of req) {
      body += chunk
      if (body.length > MAX_BODY) {
        tooBig = true
        break
      }
    }
    if (tooBig) return json(413, { verified: false, reason: "request too large" })

    let input: VerifyInput
    try {
      input = JSON.parse(body) as VerifyInput
    } catch {
      return json(400, { verified: false, reason: "invalid JSON body" })
    }

    try {
      const result = await verifyPresentation(input)
      return json(200, result)
    } catch (err) {
      // Unexpected internal error — surface as 500 so the caller fails closed.
      return json(500, { verified: false, reason: `internal error: ${(err as Error).message}` })
    }
  }

  json(404, { error: "not found" })
})

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`ack-verifier listening on :${PORT}`)
})
