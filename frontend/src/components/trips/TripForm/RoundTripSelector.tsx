import React from "react";
import { ArrowLeftRight, Weight } from "lucide-react";

import { tripRoundTripSelectorText } from "../../../resources/tr/trips";
import { cn } from "../../../lib/utils";

interface RoundTripSelectorProps {
  returnType: "none" | "empty" | "loaded";
  setReturnType: (type: "none" | "empty" | "loaded") => void;
  isReadOnly?: boolean;
}

export const RoundTripSelector: React.FC<RoundTripSelectorProps> = React.memo(
  ({ returnType, setReturnType, isReadOnly = false }) => {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-[20px] border border-border bg-base p-2.5 shadow-inner md:flex-nowrap">
        <button
          type="button"
          disabled={isReadOnly}
          onClick={() => setReturnType("none")}
          className={cn(
            "flex min-w-[100px] flex-1 items-center justify-center gap-2 rounded-xl border-2 py-4 text-xs font-black uppercase tracking-wider transition-all duration-200",
            returnType === "none"
              ? "border-text-secondary bg-text-secondary text-bg-base shadow-sm"
              : "border-transparent bg-surface text-secondary hover:border-border hover:text-primary",
          )}
        >
          <ArrowLeftRight className="h-5 w-5" />
          {tripRoundTripSelectorText.none}
        </button>
        <button
          type="button"
          disabled={isReadOnly}
          onClick={() => setReturnType("empty")}
          className={cn(
            "flex min-w-[100px] flex-1 items-center justify-center gap-2 rounded-xl border-2 py-4 text-xs font-black uppercase tracking-wider transition-all duration-200",
            returnType === "empty"
              ? "border-accent bg-accent text-bg-base shadow-accent/20"
              : "border-transparent bg-surface text-secondary hover:border-border hover:text-primary",
          )}
        >
          <ArrowLeftRight className="h-5 w-5" />
          {tripRoundTripSelectorText.empty}
        </button>
        <button
          type="button"
          disabled={isReadOnly}
          onClick={() => setReturnType("loaded")}
          className={cn(
            "flex min-w-[100px] flex-1 items-center justify-center gap-2 rounded-xl border-2 py-4 text-xs font-black uppercase tracking-wider transition-all duration-200",
            returnType === "loaded"
              ? "border-warning bg-warning text-bg-base shadow-warning/20"
              : "border-transparent bg-surface text-secondary hover:border-border hover:text-primary",
          )}
        >
          <Weight className="h-5 w-5" />
          {tripRoundTripSelectorText.loaded}
        </button>
      </div>
    );
  },
);
