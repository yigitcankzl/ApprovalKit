import { auth0 } from "@/lib/auth0";

export async function middleware(req: Request) {
  return await auth0.middleware(req);
}
