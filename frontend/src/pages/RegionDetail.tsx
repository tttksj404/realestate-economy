import { ConfidenceBar, IndicatorCard, SignalBadge } from '@/components/EconomyIndicator'
import ListingTable from '@/components/ListingTable'
import PriceChart from '@/components/PriceChart'
import Skeleton from '@/components/Skeleton'
import { useRegionDetail, useRegionListings, useRegionPrices } from '@/hooks/useEconomyData'
import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

function renderSummary(summary: string) {
  return summary.split('\n').filter(Boolean).map((line, index) => (
    <p key={`${line}-${index}`} className="text-sm leading-relaxed text-slate-200">
      {line}
    </p>
  ))
}

export default function RegionDetail() {
  const { code } = useParams<{ code: string }>()
  const regionCode = code ?? ''

  const [listingPage, setListingPage] = useState(1)
  const [propertyType, setPropertyType] = useState<string | undefined>()

  const {
    data: detail,
    isLoading: detailLoading,
    isError: detailError,
    refetch,
    isFetching,
  } = useRegionDetail(regionCode)
  const { data: listingsData, isLoading: listingsLoading } = useRegionListings(
    regionCode,
    listingPage,
    propertyType,
    Boolean(regionCode)
  )
  const { data: pricesData } = useRegionPrices(regionCode, Boolean(regionCode))

  if (detailLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-32" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={`indicator-${index}`} className="h-24" />
          ))}
        </div>
      </div>
    )
  }

  if (detailError || !detail) {
    return (
      <div className="mx-auto mt-12 max-w-lg rounded-2xl border border-red-800/40 bg-red-950/20 p-6 text-center">
        <AlertCircle className="mx-auto text-red-400" />
        <p className="mt-2 text-sm text-red-200">지역 데이터를 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-red-300/80">region: {regionCode}</p>
        <button onClick={() => refetch()} className="mt-4 rounded-xl bg-red-600 px-4 py-2 text-sm text-white">
          다시 시도
        </button>
      </div>
    )
  }

  const listings = listingsData?.listings ?? detail.recent_listings
  const total = listingsData?.total ?? listings.length
  const page = listingsData?.page ?? listingPage
  const prices = pricesData?.prices ?? detail.price_trend

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={14} />
        대시보드로
      </Link>

      <section className="rounded-2xl border border-slate-700/50 bg-slate-800/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">{detail.region_name}</h1>
            <div className="mt-2 flex items-center gap-2">
              <SignalBadge signal={detail.signal} />
              <span className="text-sm text-slate-400">신뢰도 {detail.confidence}%</span>
            </div>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 disabled:opacity-50"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
            갱신
          </button>
        </div>
        <div className="mt-4 max-w-md">
          <ConfidenceBar confidence={detail.confidence} signal={detail.signal} />
        </div>
        <div className="mt-4 space-y-1 rounded-xl bg-blue-950/30 p-4">{renderSummary(detail.summary)}</div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">6개 핵심 지표</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {detail.indicators.map((indicator) => (
            <IndicatorCard key={indicator.name} indicator={indicator} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">가격 차트</h2>
        <PriceChart data={prices} title={`${detail.region_name} 가격 추이`} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">매물 테이블</h2>
        <ListingTable
          listings={listings}
          total={total}
          page={page}
          onPageChange={setListingPage}
          selectedType={propertyType}
          onTypeFilter={(nextType) => {
            setPropertyType(nextType)
            setListingPage(1)
          }}
          isLoading={listingsLoading}
        />
      </section>
    </div>
  )
}

