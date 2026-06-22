import { useState } from "react";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Clock, MapPin, Truck, User, XCircle } from "lucide-react";
import { toast } from "sonner";

import { tripService } from "../../api/trips";
import { Trip } from "../../types";
import { Button } from "../ui/Button";

function TripOnayCard({
  trip,
  onOnayla,
  onReddet,
}: {
  trip: Trip;
  onOnayla: (id: number) => void;
  onReddet: (id: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-[10px] border border-border bg-elevated/30 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Truck className="h-4 w-4 shrink-0 text-accent" />
          <span className="text-sm font-bold text-primary">
            {trip.sefer_no || `#${trip.id}`}
          </span>
          <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-bold uppercase text-warning">
            Beklemede
          </span>
        </div>
        <span className="text-xs text-secondary">{trip.tarih}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-secondary">
          <MapPin className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {trip.cikis_yeri ?? "—"} → {trip.varis_yeri ?? "—"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-secondary">
          <User className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {(trip as any).sofor?.ad_soyad ?? `Şoför #${trip.sofor_id}`}
          </span>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <Button
          variant="primary"
          className="h-8 flex-1 gap-1.5 text-xs font-bold"
          onClick={() => onOnayla(trip.id!)}
        >
          <CheckCircle className="h-3.5 w-3.5" />
          Onayla
        </Button>
        <Button
          variant="secondary"
          className="h-8 flex-1 gap-1.5 text-xs font-bold text-danger hover:bg-danger/10"
          onClick={() => onReddet(trip.id!)}
        >
          <XCircle className="h-3.5 w-3.5" />
          Reddet
        </Button>
      </div>
    </div>
  );
}

export function TelegramOnayPanel() {
  const queryClient = useQueryClient();
  const [_loadingId, setLoadingId] = useState<number | null>(null);

  const {
    data: beklemede = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["trips", "beklemede"],
    queryFn: () => tripService.getBeklemede(0, 50),
    refetchInterval: 30_000,
  });

  const onaylaMutation = useMutation({
    mutationFn: (id: number) => tripService.onayla(id),
    onMutate: (id) => setLoadingId(id),
    onSuccess: (_, id) => {
      toast.success(`Sefer #${id} onaylandı`);
      queryClient.invalidateQueries({ queryKey: ["trips", "beklemede"] });
    },
    onError: () => toast.error("Onaylama başarısız"),
    onSettled: () => setLoadingId(null),
  });

  const reddetMutation = useMutation({
    mutationFn: (id: number) => tripService.reddet(id),
    onMutate: (id) => setLoadingId(id),
    onSuccess: (_, id) => {
      toast.success(`Sefer #${id} reddedildi`);
      queryClient.invalidateQueries({ queryKey: ["trips", "beklemede"] });
    },
    onError: () => toast.error("Reddetme başarısız"),
    onSettled: () => setLoadingId(null),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-secondary">
        <Clock className="mr-2 h-4 w-4 animate-spin" />
        Yükleniyor...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-[10px] border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
        Bekleyen seferler yüklenemedi.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold text-primary">
          <Clock className="h-4 w-4 text-warning" />
          Telegram — Onay Bekleyen Seferler
          {beklemede.length > 0 && (
            <span className="rounded-full bg-warning/15 px-2 py-0.5 text-[11px] font-bold text-warning">
              {beklemede.length}
            </span>
          )}
        </h3>
      </div>

      {beklemede.length === 0 ? (
        <div className="rounded-[10px] border border-border bg-elevated/20 p-6 text-center text-sm text-secondary">
          Onay bekleyen sefer yok
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {beklemede.map((trip) => (
            <TripOnayCard
              key={trip.id}
              trip={trip}
              onOnayla={(id) => onaylaMutation.mutate(id)}
              onReddet={(id) => reddetMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
