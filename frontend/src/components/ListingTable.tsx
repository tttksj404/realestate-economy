import { useState } from 'react'
import { ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react'
import type { Listing } from '@/types'

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
type SortDir = 'asc' | 'desc'

function formatPrice(price: number): string {
  if (price >= 10000) {
    const uk = Math.floor(price / 10000)
    const man = price % 10000
    return man > 0 ? `${uk}억 ${man.toLocaleString()}만` : `${uk}억`
  }
  return `${price.toLocaleString()}만`
}

function formatArea(area: number): string {
  const pyeong = (area / 3.305785).toFixed(1)
  return `${area}㎡ (${pyeong}평)`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('ko-KR', { year: '2-digit', month: '2-digit', day: '2-digit' })
}

const PROPERTY_TYPES = ['전체', '아파트', '빌라', '오피스텔', '단독주택', '상가'] as const

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
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const perPage = 10
  const totalPages = Math.ceil(total / perPage)

  const sorted = [...listings].sort((a, b) => {
    let comparison = 0
    if (sortKey === 'price') comparison = a.price - b.price
    else if (sortKey === 'area') comparison = a.area - b.area
    else if (sortKey === 'listed_at')
      comparison = new Date(a.listed_at).getTime() - new Date(b.listed_at).getTime()
    return sortDir === 'asc' ? comparison : -comparison
  })

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const typeColors: Record<string, string> = {
    아파트: 'bg-blue-900/50 text-blue-300 border-blue-700/50',
    빌라: 'bg-purple-900/50 text-purple-300 border-purple-700/50',
    오피스텔: 'bg-cyan-900/50 text-cyan-300 border-cyan-700/50',
    단독주택: 'bg-orange-900/50 text-orange-300 border-orange-700/50',
    상가: 'bg-pink-900/50 text-pink-300 border-pink-700/50',
  }

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/60 overflow-hidden">
      {/* Header + Filters */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-200">
          최근 매물 <span className="text-slate-500 font-normal">({total.toLocaleString()}건)</span>
        </h3>
        <div className="flex gap-1.5">
          {PROPERTY_TYPES.map((t) => {
            const value = t === '전체' ? undefined : t
            const active = (t === '전체' && !selectedType) || selectedType === t
            return (
              <button
                key={t}
                onClick={() => onTypeFilter?.(value)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700/60 text-slate-400 hover:bg-slate-600/60 hover:text-slate-300'
                }`}
              >
                {t}
              </button>
            )
          })}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/50 bg-slate-800/80">
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">유형</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">주소</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">
                <button
                  onClick={() => toggleSort('price')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  가격 <ArrowUpDown size={11} />
                </button>
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">
                <button
                  onClick={() => toggleSort('area')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  면적 <ArrowUpDown size={11} />
                </button>
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">층</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-400">
                <button
                  onClick={() => toggleSort('listed_at')}
                  className="flex items-center gap-1 hover:text-slate-200 transition-colors"
                >
                  등록일 <ArrowUpDown size={11} />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-slate-700/30">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-3 rounded bg-slate-700/60 animate-pulse" style={{ width: `${60 + j * 8}%` }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                  매물이 없습니다.
                </td>
              </tr>
            ) : (
              sorted.map((listing) => (
                <tr
                  key={listing.id}
                  className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors"
                >
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        typeColors[listing.type] ?? 'bg-slate-700/50 text-slate-300 border-slate-600/50'
                      }`}
                    >
                      {listing.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-300 max-w-[180px] truncate">
                    {listing.address ?? listing.district ?? listing.region}
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-100">
                    {formatPrice(listing.price)}
                  </td>
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
          <span className="text-xs text-slate-500">
            {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} / {total}건
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-700/60 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const start = Math.max(1, Math.min(page - 2, totalPages - 4))
              const pageNum = start + i
              return (
                <button
                  key={pageNum}
                  onClick={() => onPageChange(pageNum)}
                  className={`min-w-[28px] rounded-lg py-1 text-xs font-medium transition-colors ${
                    page === pageNum
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:bg-slate-700/60 hover:text-slate-200'
                  }`}
                >
                  {pageNum}
                </button>
              )
            })}
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-700/60 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
