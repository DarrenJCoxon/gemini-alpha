/**
 * Seed script for populating the database with quality asset universe.
 *
 * Story 5.2: Asset Universe Reduction
 *
 * This script seeds the database with a reduced quality asset universe
 * (8-10 assets) with tiered allocation limits. It also deactivates
 * excluded assets (meme coins, micro-caps).
 *
 * This script is executed via `npx prisma db seed` or `pnpm db:seed`.
 * It uses upsert to safely re-run without creating duplicates.
 */

import { PrismaClient, Prisma } from "../generated/client";

const prisma = new PrismaClient();

// Asset tier enum values (must match Python AssetTier)
const AssetTier = {
  TIER_1: "TIER_1",
  TIER_2: "TIER_2",
  TIER_3: "TIER_3",
  EXCLUDED: "EXCLUDED",
} as const;

// Tier configuration with allocation limits and thresholds
interface TierConfig {
  tier: string;
  maxAllocationPercent: Prisma.Decimal;
  minVolume24h: Prisma.Decimal;
  minMarketCap: Prisma.Decimal;
}

const TIER_CONFIGS: Record<string, TierConfig> = {
  [AssetTier.TIER_1]: {
    tier: AssetTier.TIER_1,
    maxAllocationPercent: new Prisma.Decimal("60.0"),
    minVolume24h: new Prisma.Decimal("1000000000"), // $1B
    minMarketCap: new Prisma.Decimal("50000000000"), // $50B
  },
  [AssetTier.TIER_2]: {
    tier: AssetTier.TIER_2,
    maxAllocationPercent: new Prisma.Decimal("30.0"),
    minVolume24h: new Prisma.Decimal("100000000"), // $100M
    minMarketCap: new Prisma.Decimal("5000000000"), // $5B
  },
  [AssetTier.TIER_3]: {
    tier: AssetTier.TIER_3,
    maxAllocationPercent: new Prisma.Decimal("10.0"),
    minVolume24h: new Prisma.Decimal("50000000"), // $50M
    minMarketCap: new Prisma.Decimal("1000000000"), // $1B
  },
};

/**
 * Quality asset universe with tier assignments (Story 5.2).
 * Reduced from 30 to 8-10 high-quality, liquid assets.
 */
const QUALITY_ASSETS = [
  // Tier 1: BTC, ETH - 60% max allocation
  { symbol: "BTCUSD", name: "Bitcoin", tier: AssetTier.TIER_1 },
  { symbol: "ETHUSD", name: "Ethereum", tier: AssetTier.TIER_1 },
  // Tier 2: SOL, AVAX, LINK - 30% max allocation
  { symbol: "SOLUSD", name: "Solana", tier: AssetTier.TIER_2 },
  { symbol: "AVAXUSD", name: "Avalanche", tier: AssetTier.TIER_2 },
  { symbol: "LINKUSD", name: "Chainlink", tier: AssetTier.TIER_2 },
  // Tier 3: Configurable high-conviction picks - 10% max allocation
  // Default picks (can be overridden via TIER_3_ASSETS env var in Python bot)
  { symbol: "AAVEUSD", name: "Aave", tier: AssetTier.TIER_3 },
  { symbol: "UNIUSD", name: "Uniswap", tier: AssetTier.TIER_3 },
  { symbol: "ARBUSD", name: "Arbitrum", tier: AssetTier.TIER_3 },
];

/**
 * Excluded assets - meme coins and micro-caps that should not be traded.
 */
const EXCLUDED_ASSETS = [
  { symbol: "DOGEUSD", name: "Dogecoin", reason: "Meme coin - high volatility, unpredictable" },
  { symbol: "SHIBUSD", name: "Shiba Inu", reason: "Meme coin - no fundamental value" },
  { symbol: "PEPEUSD", name: "Pepe", reason: "Meme coin - speculative only" },
  { symbol: "FLOKIUSD", name: "Floki", reason: "Meme coin - community driven" },
  { symbol: "BONKUSD", name: "Bonk", reason: "Meme coin - Solana ecosystem meme" },
];

/**
 * Previously seeded assets that should be deactivated (not in quality universe).
 */
const DEACTIVATE_ASSETS = [
  "DOTUSD", "ADAUSD", "MATICUSD", "ATOMUSD", "XLMUSD", "ALGOUSD",
  "NEARUSD", "FILUSD", "APTUSD", "OPUSD", "INJUSD", "SUIUSD",
  "TIAUSD", "IMXUSD", "RNDRUSD", "GRTUSD", "SANDUSD", "MANAUSD",
  "MKRUSD", "SNXUSD", "COMPUSD", "LDOUSD",
];

async function main(): Promise<void> {
  console.log("Starting database seed (Story 5.2: Quality Asset Universe)...");
  console.log(`Seeding ${QUALITY_ASSETS.length} quality assets...`);

  // Step 1: Seed quality assets
  for (const asset of QUALITY_ASSETS) {
    const tierConfig = TIER_CONFIGS[asset.tier];

    await prisma.asset.upsert({
      where: { symbol: asset.symbol },
      update: {
        name: asset.name,
        isActive: true,
        tier: tierConfig.tier,
        maxAllocationPercent: tierConfig.maxAllocationPercent,
        minVolume24h: tierConfig.minVolume24h,
        minMarketCap: tierConfig.minMarketCap,
        isMemeCoin: false,
        exclusionReason: null,
      },
      create: {
        symbol: asset.symbol,
        name: asset.name,
        isActive: true,
        tier: tierConfig.tier,
        maxAllocationPercent: tierConfig.maxAllocationPercent,
        minVolume24h: tierConfig.minVolume24h,
        minMarketCap: tierConfig.minMarketCap,
        isMemeCoin: false,
      },
    });

    console.log(`  + ${asset.symbol}: ${asset.name} (${asset.tier})`);
  }

  // Step 2: Mark excluded assets
  console.log(`\nMarking ${EXCLUDED_ASSETS.length} excluded assets...`);
  for (const asset of EXCLUDED_ASSETS) {
    await prisma.asset.upsert({
      where: { symbol: asset.symbol },
      update: {
        name: asset.name,
        isActive: false,
        tier: AssetTier.EXCLUDED,
        isMemeCoin: true,
        exclusionReason: asset.reason,
        maxAllocationPercent: new Prisma.Decimal("0"),
      },
      create: {
        symbol: asset.symbol,
        name: asset.name,
        isActive: false,
        tier: AssetTier.EXCLUDED,
        isMemeCoin: true,
        exclusionReason: asset.reason,
        maxAllocationPercent: new Prisma.Decimal("0"),
      },
    });

    console.log(`  x ${asset.symbol}: ${asset.reason}`);
  }

  // Step 3: Deactivate non-universe assets
  console.log(`\nDeactivating ${DEACTIVATE_ASSETS.length} non-universe assets...`);
  for (const symbol of DEACTIVATE_ASSETS) {
    const existing = await prisma.asset.findUnique({ where: { symbol } });
    if (existing) {
      await prisma.asset.update({
        where: { symbol },
        data: {
          isActive: false,
          tier: AssetTier.EXCLUDED,
          exclusionReason: "Not in quality asset universe",
        },
      });
      console.log(`  - ${symbol}: Deactivated`);
    }
  }

  // Summary
  const totalAssets = await prisma.asset.count();
  const activeAssets = await prisma.asset.count({ where: { isActive: true } });

  console.log(`\n${"=".repeat(60)}`);
  console.log("Seed completed successfully!");
  console.log(`Total assets in database: ${totalAssets}`);
  console.log(`Active assets (quality universe): ${activeAssets}`);
  console.log(`${"=".repeat(60)}`);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error("Seed failed:", e);
    await prisma.$disconnect();
    process.exit(1);
  });
