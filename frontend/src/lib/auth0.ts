import { Auth0Client } from "@auth0/nextjs-auth0/server";

const SECRET = process.env.AUTH0_SECRET || "approvalkit-dev-secret";

export const auth0 = new Auth0Client({
  domain: process.env.AUTH0_DOMAIN!,
  clientId: process.env.AUTH0_CLIENT_ID!,
  clientSecret: process.env.AUTH0_CLIENT_SECRET!,
  appBaseUrl: process.env.AUTH0_BASE_URL || "http://localhost:3000",
  secret: SECRET,
  authorizationParameters: {
    audience: `https://${process.env.AUTH0_DOMAIN}/me/`,
    scope: "openid profile email offline_access create:me:connected_accounts read:me:connected_accounts delete:me:connected_accounts",
  },
});

export async function getAuth0ClientFromRequest(): Promise<Auth0Client> {
  return auth0;
}
