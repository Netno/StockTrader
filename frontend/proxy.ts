import { withAuth } from "next-auth/middleware";
import type { NextRequest } from "next/server";

const authMiddleware = withAuth({
  pages: { signIn: "/login" },
});

export function proxy(req: NextRequest) {
  return (authMiddleware as any)(req);
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
