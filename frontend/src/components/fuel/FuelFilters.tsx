import { Calendar, Search, Filter } from "lucide-react";
import { useFuelResources } from "../../resources/useResources";
interface FuelFiltersProps {
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  vehicleFilter: string;
  setVehicleFilter: (value: string) => void;
  vehicles: { id: number; plaka: string }[];
  onFilter: () => void;
  onReset?: () => void;
}

export function FuelFilters({
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  vehicleFilter,
  setVehicleFilter,
  vehicles,
  onFilter,
  onReset,
}: FuelFiltersProps) {
  const { fuelFilterText } = useFuelResources();
  return (
    <div className="bg-surface p-4 flex flex-col md:flex-row gap-4 items-center justify-between border border-border rounded-2xl shadow-sm">
      <div className="flex items-center gap-4 w-full md:w-auto">
        <div className="relative w-full md:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="w-4 h-4 text-secondary" />
          </div>
          <select
            value={vehicleFilter}
            onChange={(event) => setVehicleFilter(event.target.value)}
            className="block w-full h-10 pl-10 pr-3 py-2 border border-border rounded-lg leading-5 bg-elevated text-primary focus:outline-none focus:ring-2 focus:ring-accent/20 sm:text-sm appearance-none transition-all"
          >
            <option value="">{fuelFilterText.vehiclePlaceholder}</option>
            {vehicles.map((vehicle) => (
              <option key={vehicle.id} value={vehicle.id}>
                {vehicle.plaka}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
        <div className="flex items-center gap-2 bg-elevated px-3 py-2 h-10 rounded-lg border border-border min-w-fit hover:border-accent/30 transition-colors">
          <Calendar className="w-4 h-4 text-secondary" />
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="bg-transparent border-none text-primary text-xs font-bold p-0 focus:ring-0 outline-none w-[110px] uppercase"
          />
          <span className="text-secondary">-</span>
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="bg-transparent border-none text-primary text-xs font-bold p-0 focus:ring-0 outline-none w-[110px] uppercase"
          />
        </div>
        <button
          onClick={onFilter}
          className="flex items-center gap-2 bg-accent/10 px-4 h-10 rounded-lg border border-accent/20 text-accent text-xs font-bold hover:bg-accent/20 transition-all whitespace-nowrap active:scale-95"
        >
          <Filter className="w-4 h-4" />
          {fuelFilterText.apply}
        </button>

        {onReset && (
          <button
            onClick={onReset}
            className="text-xs font-bold text-secondary hover:text-primary transition-colors px-2"
          >
            {fuelFilterText.reset}
          </button>
        )}
      </div>
    </div>
  );
}
