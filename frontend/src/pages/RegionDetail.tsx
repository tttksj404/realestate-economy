import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertCircle, RefreshCw } from 'lucide-react'
import { useRegionDetail, useRegionListings, useRegionPrices } from '@/hooks/useEconomyData'
import { SignalBadge, ConfidenceBar, IndicatorCard } from '@/components/EconomyIndicator'
import PriceChart from '@/components/PriceChart'
import ListingTable from '@/components/ListingTable'

export default function RegionDetail() {
  const { code } = useParams<{ code: string }>()
  const regionCode = code ?? ''

  const [listingPage, setListingPage] = useState(1)
  const [propertyType, setPropertyType] = useState<string | undefined>()

  const { data: detail, isLoading: detailLoading, isError: detailError, refetch } = useRegionDetail(regionCode)
  const { data: listingsData, isLoading: listingsLoading } = useRegionListings(regionCode, listingPage, propertyType)
  const { data: pricesData } = useRegionPrices(regionCode)

  if (detailLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-32 rounded-lg bg-slate-700/60" />
        <div className="h-28 rounded-2xl bg-slate-800/60" />
        <div className="grid grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-slate-800/60" />
          ))}
        </div>
        <div className="h-80 rounded-2xl bg-slate-800/60" />
      </div>
    )
  }

  if (detailError || !detail) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <AlertCircle size={48} className="mb-4 text-red-400" />
        <h2 className="text-lg font-semibold text-slate-200">지역 데이터를 불러올 수 없습니다</h2>
        <p className="mt-1 text-sm text-slate-500">지역 코드: {regionCode}</p>
        <div className="mt-4 flex gap-3">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-800/60 px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft size={14} /> 대시보드로
          </Link>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
          >
            <RefreshCw size={14} /> 다시 시도
          </button>
        </div>
      </div>
    )
  }

  const priceData = pricesData?.prices ?? detail.price_trend ?? []
  const listings = listingsData?.listings ?? detail.recent_listings ?? []
  const total = listingsData?.total ?? listings.length
  const page = listingsData?.page ?? listingPage

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Back + Header */}
      <div className="space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ArrowLeft size={14} />
          대시보드로 돌아가기
        </Link>

        <div className="rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-800/80 to-slate-900/80 p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-100">{detail.region_name}</h1>
              <div className="mt-2 flex items-center gap-3">
                <SignalBadge signal={detail.signal} size="md" />
                <span className="text-sm text-slate-400">신뢰도 {detail.confidence}%</span>
              </div>
            </div>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-800/40 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-700/60 transition-colors"
            >
              <RefreshCw size={13} />
              갱신
            </button>
          </div>

          <div className="mt-4 max-w-xl">
            <ConfidenceBar confidence={detail.confidence} signal={detail.signal} />
          </div>
        </div>
      </div>

      {/* AI Summary */}
      <div className="rounded-2xl border border-blue-900/40 bg-blue-950/20 p-5">
        <div className="mb-2 flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600/30 text-blue-400">
            <span className="text-xs">AI</span>
          </div>
          <span className="text-sm font-semibold text-blue-300">AI 분석 요약</span>
        </div>
        <p className="text-sm text-slate-300 leading-relaxed">{detail.summary}</p>
      </div>

      {/* Indicators grid */}
      {detail.indicators && detail.indicators.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">주요 지표</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {detail.indicators.map((ind, i) => (
              <IndicatorCard key={i} indicator={ind} />
            ))}
          </div>
        </section>
      )}

      {/* Price trend chart */}
      {priceData.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">가격 추이</h2>
          <PriceChart data={priceData} title={`${detail.region_name} 가격 추이`} />
        </section>
      )}

      {/* Listings table */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">매물 현황</h2>
        <ListingTable
          listings={listings}
          total={total}
          page={page}
          onPageChange={setListingPage}
          onTypeFilter={(t) => {
            setPropertyType(t)
            setListingPage(1)
          }}
          selectedType={propertyType}
          isLoading={listingsLoading}
        />
      </section>
    </div>
  )
}
