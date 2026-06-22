import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { locationService, LocationFilters } from "../api/locations";
import { LocationCreate, LocationUpdate } from "../types/location";

export const useLocations = (filters: LocationFilters = {}) => {
  const queryClient = useQueryClient();

  const useGetLocations = () =>
    useQuery({
      queryKey: ["locations", filters],
      queryFn: () => locationService.getAll(filters),
    });

  const useGetLocation = (id: number) =>
    useQuery({
      queryKey: ["location", id],
      queryFn: () => locationService.getById(id),
      enabled: !!id,
    });

  const useCreateLocation = () =>
    useMutation({
      mutationFn: (data: LocationCreate) => locationService.create(data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["locations"] });
      },
    });

  const useUpdateLocation = () =>
    useMutation({
      mutationFn: ({ id, data }: { id: number; data: LocationUpdate }) =>
        locationService.update(id, data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["locations"] });
      },
    });

  const useDeleteLocation = () =>
    useMutation({
      mutationFn: (id: number) => locationService.delete(id),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["locations"] });
      },
    });

  const useAnalyzeLocation = () =>
    useMutation({
      mutationFn: (id: number) => locationService.analyze(id),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["locations"] });
      },
    });

  const useLocationNames = () =>
    useQuery({
      queryKey: ["location-names"],
      queryFn: () => locationService.getUniqueNames(),
      staleTime: 1000 * 60 * 5,
    });

  const useGetRouteInfo = () =>
    useMutation({
      mutationFn: (params: {
        cikis_lat: number;
        cikis_lon: number;
        varis_lat: number;
        varis_lon: number;
      }) => locationService.getRouteInfo(params),
    });

  return {
    useGetLocations,
    useGetLocation,
    useCreateLocation,
    useUpdateLocation,
    useDeleteLocation,
    useAnalyzeLocation,
    useLocationNames,
    useGetRouteInfo,
  };
};
