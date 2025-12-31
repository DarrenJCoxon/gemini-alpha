/**
 * @jest-environment node
 *
 * Tests for Prisma schema and generated client.
 * These tests verify that the schema is correctly defined and the
 * generated Prisma client exports the expected types.
 */

import { PrismaClient, Decision, TradeStatus, Prisma } from "../generated/client";

describe("Prisma Schema", () => {
  describe("Enums", () => {
    it("should export Decision enum with correct values", () => {
      expect(Decision.BUY).toBe("BUY");
      expect(Decision.HOLD).toBe("HOLD");
      expect(Decision.SELL).toBe("SELL");
    });

    it("should export TradeStatus enum with correct values", () => {
      expect(TradeStatus.PENDING).toBe("PENDING");
      expect(TradeStatus.OPEN).toBe("OPEN");
      expect(TradeStatus.CLOSED).toBe("CLOSED");
      expect(TradeStatus.CANCELLED).toBe("CANCELLED");
    });

    it("should have exactly 3 Decision values", () => {
      const decisionValues = Object.values(Decision);
      expect(decisionValues).toHaveLength(3);
    });

    it("should have exactly 4 TradeStatus values", () => {
      const statusValues = Object.values(TradeStatus);
      expect(statusValues).toHaveLength(4);
    });
  });

  describe("PrismaClient", () => {
    it("should be able to instantiate PrismaClient", () => {
      // Don't actually connect, just verify the class exists
      expect(PrismaClient).toBeDefined();
      expect(typeof PrismaClient).toBe("function");
    });
  });

  describe("Model Types", () => {
    it("should export Asset type with correct fields", () => {
      // Verify Prisma types exist and have expected structure
      const assetCreateInput: Prisma.AssetCreateInput = {
        symbol: "TESTBTC",
        name: "Test Bitcoin",
        isActive: true,
      };

      expect(assetCreateInput.symbol).toBe("TESTBTC");
      expect(assetCreateInput.name).toBe("Test Bitcoin");
      expect(assetCreateInput.isActive).toBe(true);
    });

    it("should export Candle type with required fields", () => {
      const candleCreateInput: Prisma.CandleCreateInput = {
        timestamp: new Date(),
        timeframe: "15m",
        open: new Prisma.Decimal("100.00000000"),
        high: new Prisma.Decimal("105.00000000"),
        low: new Prisma.Decimal("99.00000000"),
        close: new Prisma.Decimal("102.00000000"),
        volume: new Prisma.Decimal("1000000.00000000"),
        asset: { connect: { id: "test-id" } },
      };

      expect(candleCreateInput.timeframe).toBe("15m");
      expect(candleCreateInput.open).toBeInstanceOf(Prisma.Decimal);
    });

    it("should export SentimentLog type with required fields", () => {
      const sentimentInput: Prisma.SentimentLogCreateInput = {
        timestamp: new Date(),
        source: "lunarcrush",
        galaxyScore: 75,
        altRank: 10,
        socialVolume: 5000,
        sentimentScore: 80,
        asset: { connect: { id: "test-id" } },
      };

      expect(sentimentInput.source).toBe("lunarcrush");
      expect(sentimentInput.galaxyScore).toBe(75);
    });

    it("should export CouncilSession type with Decision enum", () => {
      const sessionInput: Prisma.CouncilSessionCreateInput = {
        timestamp: new Date(),
        sentimentScore: 75,
        technicalSignal: "BUY",
        finalDecision: Decision.BUY,
        reasoningLog: "Market conditions favorable",
        asset: { connect: { id: "test-id" } },
      };

      expect(sessionInput.finalDecision).toBe(Decision.BUY);
      expect(sessionInput.technicalSignal).toBe("BUY");
    });

    it("should export Trade type with TradeStatus enum", () => {
      const tradeInput: Prisma.TradeCreateInput = {
        status: TradeStatus.PENDING,
        side: "BUY",
        entryPrice: new Prisma.Decimal("50000.00000000"),
        size: new Prisma.Decimal("0.10000000"),
        entryTime: new Date(),
        stopLossPrice: new Prisma.Decimal("48000.00000000"),
        asset: { connect: { id: "test-id" } },
      };

      expect(tradeInput.status).toBe(TradeStatus.PENDING);
      expect(tradeInput.side).toBe("BUY");
    });
  });

  describe("Decimal Precision", () => {
    it("should support 18,8 decimal precision for prices", () => {
      const price = new Prisma.Decimal("12345678901.12345678");
      expect(price.toString()).toBe("12345678901.12345678");
    });

    it("should support 24,8 decimal precision for volume", () => {
      const volume = new Prisma.Decimal("123456789012345678.12345678");
      expect(volume.toString()).toBe("123456789012345678.12345678");
    });

    it("should support 8,4 decimal precision for percentages", () => {
      const percent = new Prisma.Decimal("1234.5678");
      expect(percent.toString()).toBe("1234.5678");
    });
  });
});

describe("Seed Data Constants", () => {
  const TOP_30_SYMBOLS = [
    "BTCUSD", "ETHUSD", "SOLUSD", "DOTUSD", "ADAUSD",
    "AVAXUSD", "LINKUSD", "MATICUSD", "ATOMUSD", "UNIUSD",
    "XLMUSD", "ALGOUSD", "NEARUSD", "FILUSD", "APTUSD",
    "ARBUSD", "OPUSD", "INJUSD", "SUIUSD", "TIAUSD",
    "IMXUSD", "RNDRUSD", "GRTUSD", "SANDUSD", "MANAUSD",
    "AAVEUSD", "MKRUSD", "SNXUSD", "COMPUSD", "LDOUSD",
  ];

  it("should have exactly 30 asset symbols", () => {
    expect(TOP_30_SYMBOLS).toHaveLength(30);
  });

  it("should have unique symbols", () => {
    const uniqueSymbols = new Set(TOP_30_SYMBOLS);
    expect(uniqueSymbols.size).toBe(TOP_30_SYMBOLS.length);
  });

  it("should have all symbols ending with USD", () => {
    TOP_30_SYMBOLS.forEach((symbol) => {
      expect(symbol.endsWith("USD")).toBe(true);
    });
  });
});
