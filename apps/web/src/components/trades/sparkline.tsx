'use client';

import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { cn } from '@/lib/utils';

interface SparklineProps {
  data: number[]; // Array of close prices
  isPositive?: boolean;
  className?: string;
}

/**
 * A mini sparkline chart for showing price trends.
 * Uses Recharts for rendering.
 */
export function Sparkline({ data, isPositive, className }: SparklineProps) {
  // Handle empty or single data point
  if (!data || data.length < 2) {
    return (
      <div className={cn('h-8 w-20 flex items-center justify-center', className)}>
        <span className="text-xs text-zinc-500">--</span>
      </div>
    );
  }

  // Convert to chart format
  const chartData = data.map((value, index) => ({ value, index }));

  // Determine color based on trend if not specified
  const trend = isPositive ?? data[data.length - 1] > data[0];
  const color = trend ? '#10b981' : '#f43f5e'; // emerald-500 or rose-500

  return (
    <div className={cn('h-8 w-20', className)} aria-label="Price trend chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <YAxis domain={['dataMin', 'dataMax']} hide />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
