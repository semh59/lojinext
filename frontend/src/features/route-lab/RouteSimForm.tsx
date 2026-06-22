import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useLocations } from "@/hooks/use-locations";
import { routeLabText } from "@/resources/tr/routeLab";
import type { RouteSimRequest } from "@/api/route-sim";

interface Props {
  onSubmit: (req: RouteSimRequest) => void;
  submitting: boolean;
}

type Mode = "location" | "coords";

export function RouteSimForm({ onSubmit, submitting }: Props) {
  const t = routeLabText.form;
  const [mode, setMode] = useState<Mode>("location");
  const [lokasyonId, setLokasyonId] = useState<string>("");
  const [cikisLat, setCikisLat] = useState("");
  const [cikisLon, setCikisLon] = useState("");
  const [varisLat, setVarisLat] = useState("");
  const [varisLon, setVarisLon] = useState("");
  const [ton, setTon] = useState("20");
  const [aracYasi, setAracYasi] = useState("5");
  const [segLen, setSegLen] = useState("500");
  const [error, setError] = useState<string | null>(null);

  const { useGetLocations } = useLocations();
  const { data: locationsData } = useGetLocations();
  const locations = Array.isArray(locationsData)
    ? locationsData
    : locationsData?.items ?? [];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const base = {
      ton: Number(ton),
      arac_yasi: Number(aracYasi),
      segment_length_m: Number(segLen),
    };
    if (mode === "location") {
      if (!lokasyonId) {
        setError(routeLabText.empty);
        return;
      }
      onSubmit({ ...base, lokasyon_id: Number(lokasyonId) });
      return;
    }
    if (!cikisLat || !cikisLon || !varisLat || !varisLon) {
      setError(routeLabText.errors.coordsRequired);
      return;
    }
    onSubmit({
      ...base,
      cikis_lat: Number(cikisLat),
      cikis_lon: Number(cikisLon),
      varis_lat: Number(varisLat),
      varis_lon: Number(varisLon),
    });
  };

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div className="flex gap-2">
        <Button
          type="button"
          variant={mode === "location" ? "primary" : "outline"}
          onClick={() => setMode("location")}
        >
          {t.modeLocation}
        </Button>
        <Button
          type="button"
          variant={mode === "coords" ? "primary" : "outline"}
          onClick={() => setMode("coords")}
        >
          {t.modeCoords}
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {mode === "location" ? (
          <div className="flex flex-col gap-1">
            <label
              htmlFor="route-lab-loc"
              className="text-sm font-medium text-secondary"
            >
              {t.location}
            </label>
            <select
              id="route-lab-loc"
              value={lokasyonId}
              onChange={(e) => setLokasyonId(e.target.value)}
              className="rounded-card border border-border bg-elevated px-3 py-2 text-sm text-primary"
            >
              <option value="">{t.locationPlaceholder}</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.cikis_yeri} → {l.varis_yeri}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t.cikisLat}
              type="number"
              step="any"
              value={cikisLat}
              onChange={(e) => setCikisLat(e.target.value)}
            />
            <Input
              label={t.cikisLon}
              type="number"
              step="any"
              value={cikisLon}
              onChange={(e) => setCikisLon(e.target.value)}
            />
            <Input
              label={t.varisLat}
              type="number"
              step="any"
              value={varisLat}
              onChange={(e) => setVarisLat(e.target.value)}
            />
            <Input
              label={t.varisLon}
              type="number"
              step="any"
              value={varisLon}
              onChange={(e) => setVarisLon(e.target.value)}
            />
          </div>
        )}

        <div className="grid grid-cols-3 gap-3">
          <Input
            label={t.ton}
            type="number"
            step="any"
            value={ton}
            onChange={(e) => setTon(e.target.value)}
          />
          <Input
            label={t.aracYasi}
            type="number"
            value={aracYasi}
            onChange={(e) => setAracYasi(e.target.value)}
          />
          <Input
            label={t.segmentLength}
            type="number"
            value={segLen}
            onChange={(e) => setSegLen(e.target.value)}
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <Button type="submit" disabled={submitting}>
          {submitting ? t.submitting : t.submit}
        </Button>
      </form>
    </Card>
  );
}
