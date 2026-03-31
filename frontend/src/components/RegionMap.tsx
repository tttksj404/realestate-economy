import type { RegionSignal, SignalType } from '@/types'
import { useNavigate } from 'react-router-dom'

const REGIONS = [
  { code: 'seoul', name: '서울' },
  { code: 'gyeonggi', name: '경기' },
  { code: 'incheon', name: '인천' },
  { code: 'busan', name: '부산' },
  { code: 'daegu', name: '대구' },
  { code: 'daejeon', name: '대전' },
  { code: 'gwangju', name: '광주' },
  { code: 'ulsan', name: '울산' },
  { code: 'sejong', name: '세종' },
]

const signalStyles: Record<SignalType, string> = {
  boom: 'border-emerald-700/50 bg-emerald-950/30 hover:border-emerald-500/70',
  normal: 'border-amber-700/50 bg-amber-950/30 hover:border-amber-500/70',
  slump: 'border-rose-700/50 bg-rose-950/30 hover:border-rose-500/70',
}

const signalText: Record<SignalType, string> = {
  boom: '호황',
  normal: '보통',
  slump: '침체',
}

interface RegionMapProps {
  signals?: RegionSignal[]
  isLoading?: boolean
}

export default function RegionMap({ signals = [], isLoading }: RegionMapProps) {
  const navigate = useNavigate()
  const signalMap = new Map(signals.map((item) => [item.region_code, item]))

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {REGIONS.map((region) => {
        const signal = signalMap.get(region.code)
        const style = signal ? signalStyles[signal.signal] : 'border-slate-700/50 bg-slate-800/60 hover:border-slate-600/70'

        return (
          <button
            key={region.code}
            onClick={() => navigate(`/region/${region.code}`)}
            className={`rounded-2xl border p-4 text-left transition-colors ${style}`}
          >
            <p className="text-base font-semibold text-slate-100">{region.name}</p>
            {isLoading ? (
              <div className="mt-3 h-3 w-20 animate-pulse rounded bg-slate-700/70" />
            ) : signal ? (
              <>
                <p className="mt-2 text-xs text-slate-300">{signalText[signal.signal]}</p>
                <p className="mt-1 text-xs text-slate-500">신뢰도 {signal.confidence}%</p>
              </>
            ) : (
              <p className="mt-2 text-xs text-slate-500">데이터 없음</p>
            )}
          </button>
        )
      })}
    </div>
  )
}

