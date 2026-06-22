import { ArrowRight, Download, FileText, Truck, Users } from "lucide-react";
import { motion } from "framer-motion";

import type { ReportDownloadOptionId } from "../../resources/tr/reports";
import { Button } from "../ui/Button";
import { useReportsResources } from "../../resources/useResources";

interface ReportCardProps {
  onDownload: (type: ReportDownloadOptionId) => Promise<void> | void;
}

const reportCardVisuals: Record<
  ReportDownloadOptionId,
  {
    icon: typeof FileText;
    color: string;
    gradient: string;
  }
> = {
  fleet_summary: {
    icon: FileText,
    color: "bg-info/10 text-info",
    gradient: "from-info/10 to-info/5",
  },
  vehicle_detail: {
    icon: Truck,
    color: "bg-accent/10 text-accent",
    gradient: "from-accent/10 to-accent/5",
  },
  driver_comparison: {
    icon: Users,
    color: "bg-success/10 text-success",
    gradient: "from-success/10 to-success/5",
  },
};

export function ReportCards({ onDownload }: ReportCardProps) {
  const { reportCardsText, reportDownloadOptions } = useReportsResources();
  const cards = (
    Object.entries(reportDownloadOptions) as Array<
      [
        ReportDownloadOptionId,
        (typeof reportDownloadOptions)[ReportDownloadOptionId],
      ]
    >
  ).map(([id, option]) => ({
    id,
    title: option.cardTitle,
    description: option.cardDescription,
    ...reportCardVisuals[id],
  }));

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      {cards.map((card, index) => (
        <motion.div
          key={card.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
          className="group relative overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-sm transition-all hover:border-accent/40 hover:shadow-md"
        >
          <div
            className={`absolute inset-0 bg-gradient-to-br ${card.gradient} opacity-0 transition-opacity group-hover:opacity-100`}
          />

          <div className="relative z-10">
            <div
              className={`mb-6 flex h-12 w-12 items-center justify-center rounded-xl ${card.color} shadow-sm`}
            >
              <card.icon className="h-6 w-6" />
            </div>

            <h3 className="mb-2 text-xl font-bold text-primary">
              {card.title}
            </h3>
            <p className="mb-8 h-[40px] text-sm font-medium leading-relaxed text-secondary">
              {card.description}
            </p>

            <Button
              variant="secondary"
              className="w-full justify-between shadow-sm transition-all group-hover:bg-elevated"
              onClick={() => onDownload(card.id)}
            >
              <span className="flex items-center gap-2">
                <Download className="h-4 w-4" />
                {reportCardsText.downloadButton}
              </span>
              <ArrowRight className="h-4 w-4 -translate-x-2 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
            </Button>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
