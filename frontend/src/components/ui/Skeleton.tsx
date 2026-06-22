import { cn } from "../../lib/utils";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
}

export function Skeleton({
  className,
  variant = "rectangular",
}: SkeletonProps) {
  return (
    <div
      className={cn(
        "skeleton",
        variant === "text" && "h-4 w-full",
        variant === "circular" && "rounded-full",
        variant === "rectangular" && "rounded-xl",
        className,
      )}
    />
  );
}
