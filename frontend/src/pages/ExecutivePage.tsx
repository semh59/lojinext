import { LineChart } from "lucide-react";

import { BusFactorWidget } from "@/components/executive/BusFactorWidget";
import { CarbonReportCard } from "@/components/executive/CarbonReportCard";
import { CashflowProjectionChart } from "@/components/executive/CashflowProjectionChart";
import { ComplianceHeatmap } from "@/components/executive/ComplianceHeatmap";
import { CrossFeatureSavings } from "@/components/executive/CrossFeatureSavings";
import { DownloadPdfButton } from "@/components/executive/DownloadPdfButton";
import { FleetEfficiencyCard } from "@/components/executive/FleetEfficiencyCard";
import { WhatIfPanel } from "@/components/executive/WhatIfPanel";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useExecutiveResources } from "@/resources/useResources";
export default function ExecutivePage() {
  const { executiveText } = useExecutiveResources();
  usePageTitle(executiveText.pageTitle);
  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <LineChart className="mt-1 h-6 w-6 text-accent" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-primary">
              {executiveText.pageTitle}
            </h1>
            <p className="mt-1 text-sm text-secondary">
              {executiveText.pageSubtitle}
            </p>
          </div>
        </div>
        <DownloadPdfButton />
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <FleetEfficiencyCard className="md:col-span-4" />
        <CashflowProjectionChart className="md:col-span-8" />
        <BusFactorWidget className="md:col-span-6" />
        <CrossFeatureSavings className="md:col-span-6" />
        <WhatIfPanel className="md:col-span-12" />
        <CarbonReportCard className="md:col-span-6" />
        <ComplianceHeatmap className="md:col-span-6" />
      </div>
    </div>
  );
}
