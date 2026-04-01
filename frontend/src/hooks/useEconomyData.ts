import {
  getEconomyOverview,
  getMacroInterpretation,
  getRegionDetail,
  getRegionListings,
  getRegionPrices,
  getRegions,
} from '@/api/client'
import { useQuery } from '@tanstack/react-query'

export const queryKeys = {
  economyOverview: ['economy', 'overview'] as const,
  macroInterpretation: ['economy', 'macro'] as const,
  regionDetail: (code: string) => ['economy', 'region', code] as const,
  regions: ['regions'] as const,
  regionListings: (code: string, page: number, type?: string) =>
    ['regions', code, 'listings', page, type] as const,
  regionPrices: (code: string) => ['regions', code, 'prices'] as const,
}

export function useEconomyOverview() {
  return useQuery({
    queryKey: queryKeys.economyOverview,
    queryFn: getEconomyOverview,
    staleTime: 1000 * 60 * 5,
  })
}

export function useMacroInterpretation(enabled = true) {
  return useQuery({
    queryKey: queryKeys.macroInterpretation,
    queryFn: () => getMacroInterpretation(),
    enabled,
    staleTime: 1000 * 60 * 10,
  })
}

export function useRegionDetail(regionCode: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.regionDetail(regionCode),
    queryFn: () => getRegionDetail(regionCode),
    enabled: enabled && Boolean(regionCode),
    staleTime: 1000 * 60 * 5,
  })
}

export function useRegions() {
  return useQuery({
    queryKey: queryKeys.regions,
    queryFn: getRegions,
    staleTime: 1000 * 60 * 30,
  })
}

export function useRegionListings(regionCode: string, page = 1, propertyType?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.regionListings(regionCode, page, propertyType),
    queryFn: () => getRegionListings(regionCode, page, propertyType),
    enabled: enabled && Boolean(regionCode),
    staleTime: 1000 * 60 * 2,
    placeholderData: (prev) => prev,
  })
}

export function useRegionPrices(regionCode: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.regionPrices(regionCode),
    queryFn: () => getRegionPrices(regionCode),
    enabled: enabled && Boolean(regionCode),
    staleTime: 1000 * 60 * 10,
  })
}

