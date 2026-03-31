import type { Listing } from '@/types'
import { ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'

interface ListingTableProps {
  listings: Listing[]
  total: number
  page: number
  onPageChange: (page: number) => void
  onTypeFilter?: (type: string | undefined) => void
  selectedType?: string
  isLoading?: boolean
}

type SortKey = 'price' | 'area' | 'listed_at'
type SortDirection = 'asc' | 'desc'

const PROPERTY_TYPES = ['전체', '아파트', '빌라', '오피스텔', '단독주택', '상가'] as const

function formatPrice(price: number): string {
  if (price >= 10000) {
    const eok = Math.floor(price / 10000)
    const man = price % 10000
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만` : `${eok}억`
  }
  return `${price.toLocaleString()}만`
}

function formatArea(area: number): string {
  const pyeong = (area / 3.305785).toFixed(1)
  return `${area.toFixed(1)}㎡ (${pyeong}평)`
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('ko-KR')
}

export default function ListingTable({
  listings,
  total,
  page,
  onPageChange,
  onTypeFilter,
  selectedType,
  isLoading,
}: ListingTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('listed_at')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const perPage = 10
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  const sortedListings = useMemo(() => {
    return [...listings].sort((a, b) => {
      const result =
        sortKey === 'price'
          ? a.price - b.price
          : sortKey === 'area'
          ? a.area - b.area
          : new Date(a.listed_at).getTime() - new Date(b.listed_at).getTime()

      return sortDirection === 'asc' ? result : -result
    })
  }, [listings, sortDirection, sortKey])

  function toggleSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }

    setSortKey(nextKey)
    setSortDirection('desc')
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-700/50 bg-slate-800/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/50 p-4">
        <h3 className="text-sm font-semibold text-slate-200">매물 목록 ({total.toLocaleString()}건)</h3>
        <div className="flex flex-wrap gap-1.5">
          {PROPERTY_TYPES.map((type) => {
            const value = type === '전체' ? undefined : type
            const active = (type === '전체' && !selectedType) || selectedType === type
            return (
              <button
                key={type}
                onClick={() => onTypeFilter?.(value)}
                className={`rounded-full px-3 py-1 text-xs ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700/60 text-slate-300 hover:bg-slate-600/60'
                }`}
              >
                {type}
              </button>
            )
          })}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-slate-900/50 text-slate-400">
            <tr>
              <th className="px-4 py-3 text-left">유형</th>
              <th className="px-4 py-3 text-left">주소</th>
              <th className="px-4 py-3 text-left">
                <button onClick={() => toggleSort('price')} className="inline-flex items-center gap-1">
                  가격 <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="px-4 py-3 text-left">
                <button onClick={() => toggleSort('area')} className="inline-flex items-center gap-1">
                  면적 <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="px-4 py-3 text-left">층</th>
              <th className="px-4 py-3 text-left">
                <button onClick={() => toggleSort('listed_at')} className="inline-flex items-center gap-1">
                  등록일 <ArrowUpDown size={12} />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, row) => (
                <tr key={`loading-${row}`} className="border-t border-slate-700/40">
                  {Array.from({ length: 6 }).map((__, col) => (
                    <td key={`loading-${row}-${col}`} className="px-4 py-3">
                      <div className="h-3 animate-pulse rounded bg-slate-700/60" />
                    </td>
                  ))}
                </tr>
              ))
            ) : sortedListings.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-slate-500">
                  조건에 맞는 매물이 없습니다.
                </td>
              </tr>
            ) : (
              sortedListings.map((listing) => (
                <tr key={listing.id} className="border-t border-slate-700/40">
                  <td className="px-4 py-3 text-slate-200">{listing.type}</td>
                  <td className="max-w-[240px] truncate px-4 py-3 text-slate-300">
                    {listing.address ?? listing.district ?? listing.region}
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-100">{formatPrice(listing.price)}</td>
                  <td className="px-4 py-3 text-slate-300">{formatArea(listing.area)}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {listing.floor != null
                      ? `${listing.floor}층${listing.total_floors ? `/${listing.total_floors}층` : ''}`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDate(listing.listed_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-700/50 px-4 py-3 text-xs text-slate-400">
          <span>
            {(page - 1) * perPage + 1}-{Math.min(page * perPage, total)} / {total}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="rounded p-1 hover:bg-slate-700/60 disabled:opacity-40"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="px-2">
              {page}/{totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="rounded p-1 hover:bg-slate-700/60 disabled:opacity-40"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

