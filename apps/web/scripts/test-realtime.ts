#!/usr/bin/env npx tsx
/**
 * Script to test realtime by inserting records into Supabase.
 * Run while dashboard is open to verify updates appear.
 *
 * Usage: npx tsx scripts/test-realtime.ts [--session | --trade | --price]
 *
 * Prerequisites:
 * - NEXT_PUBLIC_SUPABASE_URL must be set
 * - SUPABASE_SERVICE_KEY must be set (service role key for inserting)
 */
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  console.error('Error: Missing required environment variables');
  console.error('Required: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_KEY');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

async function getFirstAssetId(): Promise<string | null> {
  const { data, error } = await supabase
    .from('assets')
    .select('id')
    .limit(1)
    .single();

  if (error) {
    console.error('Error fetching asset:', error);
    return null;
  }

  return data?.id || null;
}

async function insertTestSession() {
  console.log('Inserting test council session...');

  const assetId = await getFirstAssetId();
  if (!assetId) {
    console.error('No assets found in database. Please insert an asset first.');
    return;
  }

  const decisions = ['BUY', 'SELL', 'HOLD'] as const;
  const decision = decisions[Math.floor(Math.random() * decisions.length)];

  const { data, error } = await supabase
    .from('council_sessions')
    .insert({
      asset_id: assetId,
      timestamp: new Date().toISOString(),
      sentiment_score: Math.floor(Math.random() * 100),
      technical_signal: decision === 'BUY' ? 'BULLISH' : decision === 'SELL' ? 'BEARISH' : 'NEUTRAL',
      technical_strength: Math.floor(Math.random() * 100),
      vision_confidence: Math.floor(Math.random() * 100),
      vision_valid: true,
      final_decision: decision,
      decision_confidence: Math.floor(Math.random() * 30) + 70, // 70-100
      reasoning_log: `Test session for realtime verification. Generated at ${new Date().toISOString()}`,
    })
    .select()
    .single();

  if (error) {
    console.error('Error inserting session:', error);
  } else {
    console.log('Successfully inserted session:', data);
    console.log(`Decision: ${decision}`);
  }
}

async function insertTestTrade() {
  console.log('Inserting test trade...');

  const assetId = await getFirstAssetId();
  if (!assetId) {
    console.error('No assets found in database. Please insert an asset first.');
    return;
  }

  const entryPrice = 100 + Math.random() * 50;
  const stopLoss = entryPrice * 0.95; // 5% below entry

  const { data, error } = await supabase
    .from('trades')
    .insert({
      asset_id: assetId,
      status: 'OPEN',
      direction: 'LONG',
      entry_price: entryPrice,
      size: 0.1 + Math.random() * 0.5,
      entry_time: new Date().toISOString(),
      stop_loss_price: stopLoss,
      take_profit_price: entryPrice * 1.1, // 10% above entry
    })
    .select()
    .single();

  if (error) {
    console.error('Error inserting trade:', error);
  } else {
    console.log('Successfully inserted trade:', data);
  }
}

async function updateAssetPrice() {
  console.log('Updating asset price...');

  const assetId = await getFirstAssetId();
  if (!assetId) {
    console.error('No assets found in database. Please insert an asset first.');
    return;
  }

  // Get current price
  const { data: asset } = await supabase
    .from('assets')
    .select('last_price')
    .eq('id', assetId)
    .single();

  const currentPrice = parseFloat(asset?.last_price || '100');
  const priceChange = (Math.random() - 0.5) * 5; // +/- 2.5
  const newPrice = currentPrice + priceChange;

  const { data, error } = await supabase
    .from('assets')
    .update({ last_price: newPrice })
    .eq('id', assetId)
    .select()
    .single();

  if (error) {
    console.error('Error updating price:', error);
  } else {
    console.log(`Successfully updated price: ${currentPrice.toFixed(2)} -> ${newPrice.toFixed(2)}`);
    console.log('Asset:', data);
  }
}

// Parse command line args
const args = process.argv.slice(2);
const command = args[0] || '--session';

switch (command) {
  case '--session':
    insertTestSession();
    break;
  case '--trade':
    insertTestTrade();
    break;
  case '--price':
    updateAssetPrice();
    break;
  default:
    console.log('Usage: npx tsx scripts/test-realtime.ts [--session | --trade | --price]');
    console.log('  --session  Insert a test council session (default)');
    console.log('  --trade    Insert a test trade');
    console.log('  --price    Update asset price');
}
