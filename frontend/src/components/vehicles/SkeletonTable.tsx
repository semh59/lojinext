import { Truck } from "lucide-react";
import { useVehiclesResources } from "../../resources/useResources";

interface SkeletonTableProps {
  rows?: number;
}

function SkeletonCell({ width }: { width: string }) {
  return <div className={`h-3 bg-border rounded animate-pulse ${width}`} />;
}

export function SkeletonTable({ rows = 5 }: SkeletonTableProps) {
  const { vehicleFilterText } = useVehiclesResources();
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <table className="w-full">
        <thead>
          <tr className="bg-elevated border-b border-border">
            <th className="px-4 py-4 text-left text-xs font-bold text-secondary uppercase tracking-wider w-[180px]">
              {vehicleFilterText.skeleton.columns.vehicle}
            </th>
            <th className="px-4 py-4 text-left text-xs font-bold text-secondary uppercase tracking-wider w-[130px]">
              {vehicleFilterText.skeleton.columns.plate}
            </th>
            <th className="px-4 py-4 text-center text-xs font-bold text-secondary uppercase tracking-wider w-[70px]">
              {vehicleFilterText.skeleton.columns.year}
            </th>
            <th className="px-4 py-4 text-right text-xs font-bold text-secondary uppercase tracking-wider w-[90px]">
              {vehicleFilterText.skeleton.columns.tank}
            </th>
            <th className="px-4 py-4 text-right text-xs font-bold text-secondary uppercase tracking-wider w-[100px]">
              {vehicleFilterText.skeleton.columns.target}
            </th>
            <th className="px-4 py-4 text-center text-xs font-bold text-secondary uppercase tracking-wider w-[90px]">
              {vehicleFilterText.skeleton.columns.status}
            </th>
            <th className="px-4 py-4 text-center text-xs font-bold text-secondary uppercase tracking-wider w-[70px]">
              {vehicleFilterText.skeleton.columns.actions}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {Array.from({ length: rows }).map((_, index) => (
            <tr
              key={index}
              className="animate-pulse"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-lg bg-border flex items-center justify-center shrink-0">
                    <Truck className="w-4 h-4 text-secondary" />
                  </div>
                  <div className="space-y-1.5">
                    <SkeletonCell width="w-16" />
                    <SkeletonCell width="w-12" />
                  </div>
                </div>
              </td>
              <td className="px-4 py-3">
                <SkeletonCell width="w-20" />
              </td>
              <td className="px-4 py-3 text-center">
                <SkeletonCell width="w-10 mx-auto" />
              </td>
              <td className="px-4 py-3">
                <SkeletonCell width="w-12 ml-auto" />
              </td>
              <td className="px-4 py-3">
                <SkeletonCell width="w-14 ml-auto" />
              </td>
              <td className="px-4 py-3 text-center">
                <div className="w-14 h-5 bg-border rounded-full animate-pulse mx-auto" />
              </td>
              <td className="px-4 py-3 text-center">
                <div className="w-7 h-7 bg-border rounded-lg animate-pulse mx-auto" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
