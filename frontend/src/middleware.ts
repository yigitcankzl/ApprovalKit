import { Auth0Client } from "@auth0/nextjs-auth0/server";

const client = new Auth0Client();

export async function middleware(req: Request) {
  return await client.middleware(req);
}
