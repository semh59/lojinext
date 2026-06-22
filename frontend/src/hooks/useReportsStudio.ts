import { useQuery } from "@tanstack/react-query";
import { reportsStudioService } from "../api/reports-studio";

export function useReportTemplates() {
  return useQuery({
    queryKey: ["reports-v2", "studio", "templates"],
    queryFn: () => reportsStudioService.listTemplates(),
    staleTime: 60 * 60 * 1000, // 1 saat — statik liste
    refetchOnWindowFocus: false,
  });
}
