/**
 * Generic Skeleton Loading Components
 *
 * Reusable skeleton placeholders for loading states.
 * Formerly duplicated across DriversPage, VehiclesPage, etc.
 */

import React from "react";

interface SkeletonProps {
  className?: string;
}

/**
 * Base Skeleton with pulse animation
 */
export const Skeleton: React.FC<SkeletonProps> = ({ className = "" }) => (
  <div
    className={`animate-pulse bg-border dark:bg-elevated/40 rounded ${className}`}
  />
);

/**
 * Table Row Skeleton - for data tables
 */
interface SkeletonRowProps {
  columns?: number;
}

export const SkeletonRow: React.FC<SkeletonRowProps> = ({ columns = 6 }) => (
  <tr className="border-b border-border">
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="px-4 py-3">
        <Skeleton className="h-4 w-full" />
      </td>
    ))}
  </tr>
);

/**
 * Table Skeleton - full table with multiple rows
 */
interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

export const TableSkeleton: React.FC<TableSkeletonProps> = ({
  rows = 5,
  columns = 6,
}) => (
  <div className="overflow-hidden rounded-lg border border-border">
    <table className="min-w-full">
      <thead className="bg-elevated/50">
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} className="px-4 py-3">
              <Skeleton className="h-4 w-20" />
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, i) => (
          <SkeletonRow key={i} columns={columns} />
        ))}
      </tbody>
    </table>
  </div>
);

/**
 * Card Skeleton - for card layouts
 */
export const CardSkeleton: React.FC = () => (
  <div className="p-4 rounded-lg border border-border space-y-3">
    <Skeleton className="h-6 w-3/4" />
    <Skeleton className="h-4 w-1/2" />
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-2/3" />
  </div>
);

/**
 * Stat Card Skeleton - for dashboard stat cards
 */
export const StatSkeleton: React.FC = () => (
  <div className="p-6 rounded-xl border border-border space-y-2">
    <Skeleton className="h-4 w-24" />
    <Skeleton className="h-8 w-16" />
    <Skeleton className="h-3 w-20" />
  </div>
);

/**
 * List Skeleton - for simple lists
 */
interface ListSkeletonProps {
  items?: number;
}

export const ListSkeleton: React.FC<ListSkeletonProps> = ({ items = 5 }) => (
  <div className="space-y-3">
    {Array.from({ length: items }).map((_, i) => (
      <div key={i} className="flex items-center space-x-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
    ))}
  </div>
);

export default {
  Skeleton,
  SkeletonRow,
  TableSkeleton,
  CardSkeleton,
  StatSkeleton,
  ListSkeleton,
};
