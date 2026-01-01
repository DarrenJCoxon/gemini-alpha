'use client';

import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  flexRender,
  ColumnDef,
  Column,
} from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { ScannerAsset } from '@/types/scanner';
import { TrendingUp, TrendingDown, Minus, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

interface ScannerTableProps {
  assets: ScannerAsset[];
  onRowClick?: (asset: ScannerAsset) => void;
  className?: string;
}

interface SortableHeaderProps {
  column: Column<ScannerAsset, unknown>;
  children: React.ReactNode;
}

/**
 * Sortable table displaying market assets with sentiment and technical data.
 * Uses TanStack Table for sorting functionality.
 */
export function ScannerTable({ assets, onRowClick, className }: ScannerTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'sentimentScore', desc: false }, // Low sentiment (fear) first
  ]);

  const columns: ColumnDef<ScannerAsset>[] = useMemo(
    () => [
      {
        accessorKey: 'symbol',
        header: ({ column }) => (
          <SortableHeader column={column}>Symbol</SortableHeader>
        ),
        cell: ({ row }) => (
          <span className="font-mono font-semibold text-zinc-100">
            {row.original.symbol}
          </span>
        ),
      },
      {
        accessorKey: 'lastPrice',
        header: ({ column }) => (
          <SortableHeader column={column}>Price</SortableHeader>
        ),
        cell: ({ row }) => (
          <div className="font-mono text-right">
            <span className="text-zinc-100">
              ${row.original.lastPrice.toFixed(2)}
            </span>
            <div
              className={cn(
                'text-xs',
                row.original.priceChange15m >= 0 ? 'text-emerald-500' : 'text-rose-500'
              )}
            >
              {row.original.priceChange15m >= 0 ? '+' : ''}
              {row.original.priceChange15m.toFixed(2)}%
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'sentimentScore',
        header: ({ column }) => (
          <SortableHeader column={column}>Fear</SortableHeader>
        ),
        cell: ({ row }) => {
          const score = row.original.sentimentScore;
          if (score === null) {
            return <span className="text-zinc-500">--</span>;
          }

          // Lower score = more fear = green (buying opportunity)
          const colorClass = score < 20
            ? 'text-emerald-500'
            : score < 40
            ? 'text-emerald-400'
            : score < 60
            ? 'text-zinc-400'
            : score < 80
            ? 'text-rose-400'
            : 'text-rose-500';

          return (
            <span className={cn('font-mono', colorClass)}>
              {score}
            </span>
          );
        },
        sortingFn: (rowA, rowB) => {
          const a = rowA.original.sentimentScore ?? 999;
          const b = rowB.original.sentimentScore ?? 999;
          return a - b;
        },
      },
      {
        accessorKey: 'technicalSignal',
        header: ({ column }) => (
          <SortableHeader column={column}>Signal</SortableHeader>
        ),
        cell: ({ row }) => {
          const signal = row.original.technicalSignal;
          if (!signal) {
            return <span className="text-zinc-500">--</span>;
          }

          const Icon = signal === 'BULLISH'
            ? TrendingUp
            : signal === 'BEARISH'
            ? TrendingDown
            : Minus;

          const colorClass = signal === 'BULLISH'
            ? 'text-emerald-500'
            : signal === 'BEARISH'
            ? 'text-rose-500'
            : 'text-zinc-400';

          return (
            <div className={cn('flex items-center gap-1', colorClass)}>
              <Icon className="h-3 w-3" aria-hidden="true" />
              <span className="text-xs">{signal}</span>
            </div>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: assets,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className={cn('rounded-md border border-zinc-800', className)}>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="border-zinc-800 hover:bg-transparent">
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className="text-zinc-400 text-xs h-9"
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length > 0 ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={cn(
                  'border-zinc-800 transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-zinc-800/50'
                )}
                onClick={() => onRowClick?.(row.original)}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={onRowClick ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onRowClick(row.original);
                  }
                } : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className="py-2 text-sm">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="h-24 text-center text-zinc-500"
              >
                No assets found
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function SortableHeader({ column, children }: SortableHeaderProps) {
  const sorted = column.getIsSorted();

  return (
    <button
      className="flex items-center gap-1 hover:text-zinc-100 transition-colors"
      onClick={() => column.toggleSorting(sorted === 'asc')}
      aria-label={`Sort by ${children}${sorted ? `, currently ${sorted === 'asc' ? 'ascending' : 'descending'}` : ''}`}
    >
      {children}
      {sorted === 'asc' ? (
        <ArrowUp className="h-3 w-3" aria-hidden="true" />
      ) : sorted === 'desc' ? (
        <ArrowDown className="h-3 w-3" aria-hidden="true" />
      ) : (
        <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden="true" />
      )}
    </button>
  );
}
