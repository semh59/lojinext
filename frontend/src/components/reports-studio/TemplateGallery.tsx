import { motion } from "framer-motion";
import {
  BarChart3,
  FileText,
  Fuel,
  Leaf,
  LineChart,
  Truck,
} from "lucide-react";

import { cn } from "../../lib/utils";
import { reportsStudioText } from "../../resources/tr/reports-studio";
import type {
  TemplateCategory,
  TemplateId,
  TemplateMeta,
} from "../../api/reports-studio";

const TEMPLATE_ICONS: Record<TemplateId, typeof FileText> = {
  ceo_1pager: FileText,
  fleet_weekly: BarChart3,
  fuel_cost_analysis: Fuel,
  vehicle_comparison: Truck,
  carbon_report: Leaf,
  what_if: LineChart,
};

const CATEGORY_STYLES: Record<TemplateCategory, string> = {
  executive: "bg-accent/10 text-accent border-accent/30",
  fleet: "bg-info/10 text-info border-info/30",
  fuel: "bg-warning/10 text-warning border-warning/30",
  compliance: "bg-success/10 text-success border-success/30",
};

interface TemplateGalleryProps {
  templates: TemplateMeta[];
  selectedId: TemplateId | null;
  onSelect: (template: TemplateMeta) => void;
}

export function TemplateGallery({
  templates,
  selectedId,
  onSelect,
}: TemplateGalleryProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {templates.map((tmpl, index) => {
        const Icon = TEMPLATE_ICONS[tmpl.id] ?? FileText;
        const isSelected = selectedId === tmpl.id;
        return (
          <motion.button
            key={tmpl.id}
            type="button"
            onClick={() => onSelect(tmpl)}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
            className={cn(
              "group relative flex flex-col gap-3 rounded-modal border bg-surface p-5 text-left shadow-sm transition-all",
              isSelected
                ? "border-accent ring-2 ring-accent/30"
                : "border-border hover:border-accent/40 hover:shadow-md",
            )}
            data-testid={`template-card-${tmpl.id}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-card border",
                  CATEGORY_STYLES[tmpl.category],
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
              <span
                className={cn(
                  "rounded-card border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                  CATEGORY_STYLES[tmpl.category],
                )}
              >
                {reportsStudioText.categoryLabels[tmpl.category]}
              </span>
            </div>
            <div>
              <h3 className="text-base font-semibold text-primary">
                {tmpl.title}
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-secondary">
                {tmpl.description}
              </p>
            </div>
            <div className="mt-auto flex items-center gap-1.5">
              {tmpl.formats.map((fmt) => (
                <span
                  key={fmt}
                  className="rounded-card bg-elevated px-2 py-0.5 text-[10px] font-semibold uppercase text-tertiary"
                >
                  {fmt}
                </span>
              ))}
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
