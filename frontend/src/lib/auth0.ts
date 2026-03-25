import { Auth0Client } from "@auth0/nextjs-auth0/server";

const domain = process.env.AUTH0_DOMAIN || process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "";

export const auth0 = new Auth0Client({
  authorizationParameters: {
    audience: `https://${domain}/me/`,
    scope: "openid profile email offline_access create:me:connected_accounts read:me:connected_accounts delete:me:connected_accounts",
  },
});
