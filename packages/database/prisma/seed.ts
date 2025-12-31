/**
 * Seed script for populating the database with Top 30 Kraken trading pairs.
 *
 * This script is executed via `npx prisma db seed` or `pnpm db:seed`.
 * It uses upsert to safely re-run without creating duplicates.
 */

import { PrismaClient } from "../generated/client";

const prisma = new PrismaClient();

/**
 * Top 30 Kraken trading pairs for the Contrarian AI system.
 * These are selected based on liquidity, market cap, and trading volume.
 */
const TOP_30_ASSETS = [
  { symbol: "BTCUSD", name: "Bitcoin" },
  { symbol: "ETHUSD", name: "Ethereum" },
  { symbol: "SOLUSD", name: "Solana" },
  { symbol: "DOTUSD", name: "Polkadot" },
  { symbol: "ADAUSD", name: "Cardano" },
  { symbol: "AVAXUSD", name: "Avalanche" },
  { symbol: "LINKUSD", name: "Chainlink" },
  { symbol: "MATICUSD", name: "Polygon" },
  { symbol: "ATOMUSD", name: "Cosmos" },
  { symbol: "UNIUSD", name: "Uniswap" },
  { symbol: "XLMUSD", name: "Stellar" },
  { symbol: "ALGOUSD", name: "Algorand" },
  { symbol: "NEARUSD", name: "NEAR Protocol" },
  { symbol: "FILUSD", name: "Filecoin" },
  { symbol: "APTUSD", name: "Aptos" },
  { symbol: "ARBUSD", name: "Arbitrum" },
  { symbol: "OPUSD", name: "Optimism" },
  { symbol: "INJUSD", name: "Injective" },
  { symbol: "SUIUSD", name: "Sui" },
  { symbol: "TIAUSD", name: "Celestia" },
  { symbol: "IMXUSD", name: "Immutable X" },
  { symbol: "RNDRUSD", name: "Render" },
  { symbol: "GRTUSD", name: "The Graph" },
  { symbol: "SANDUSD", name: "The Sandbox" },
  { symbol: "MANAUSD", name: "Decentraland" },
  { symbol: "AAVEUSD", name: "Aave" },
  { symbol: "MKRUSD", name: "Maker" },
  { symbol: "SNXUSD", name: "Synthetix" },
  { symbol: "COMPUSD", name: "Compound" },
  { symbol: "LDOUSD", name: "Lido DAO" },
];

async function main(): Promise<void> {
  console.log("Starting database seed...");
  console.log(`Seeding ${TOP_30_ASSETS.length} assets...`);

  let created = 0;
  let updated = 0;

  for (const asset of TOP_30_ASSETS) {
    const result = await prisma.asset.upsert({
      where: { symbol: asset.symbol },
      update: {
        name: asset.name,
        isActive: true,
      },
      create: {
        symbol: asset.symbol,
        name: asset.name,
        isActive: true,
      },
    });

    // Check if this was a create or update
    const existingAsset = await prisma.asset.findUnique({
      where: { symbol: asset.symbol },
    });

    if (existingAsset && existingAsset.createdAt.getTime() === result.createdAt.getTime()) {
      // The createdAt matches, could be either - we'll count based on upsert logic
    }
    created++;
    console.log(`  - ${asset.symbol}: ${asset.name}`);
  }

  const totalAssets = await prisma.asset.count();
  console.log(`\nSeed completed successfully!`);
  console.log(`Total assets in database: ${totalAssets}`);
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
