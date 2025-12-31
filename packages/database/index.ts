/**
 * Contrarian AI Database Package
 *
 * Exports the Prisma Client for use in the Next.js frontend.
 * The Python bot uses SQLModel with the same database.
 */

import { PrismaClient } from "./generated/client";

// Prevent multiple instances in development (hot reload)
const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log:
      process.env.NODE_ENV === "development"
        ? ["query", "error", "warn"]
        : ["error"],
  });

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

// Re-export everything from generated client
export * from "./generated/client";

// Default export for convenience
export default prisma;
