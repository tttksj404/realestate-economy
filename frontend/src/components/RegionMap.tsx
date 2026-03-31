import { useNavigate } from 'react-router-dom'
import type { SignalType, RegionSignal } from '@/types'

const FIXED_REGIONS: { code: string; name: string; emoji: string }[] = [
  { code: 'seoul', name: '서울', emoji: '🏙️' },
  { code: 'gyeonggi', name: '경기', emoji: '🌄' },
  { code: 'incheon', name: '인천', emoji: '✈️' },
  { code: 'busan', name: '부산', emoji: '🌊' },
  { code: 'daegu', name: '대구', emoji: '🏔️' },
  { code: 'daejeon', name: '대전', emoji: '🔬' },
  { code: 'gwangju', name: '광주', emoji: '🎨' },
  { code: 'ulsan', name: '울산', emoji: '🏭' },
  { code: 'sejong', name: '세종', emoji: '🏛️' },
]

const signalStyles: Record<SignalType, { card: string; dot: string; badge: string; glow: string }> = {
  boom: {
    card: 'border-green-700/60 bg-green-950/40 hover:border-green-500/80 hover:bg-green-900/40',
    dot: 'bg-green-400',
    badge: 'bg-green-900/60 text-green-400',
    glow: 'shadow-green-900/30',
  },
  normal: {
    card: 'border-yellow-700/60 bg-yellow-950/30 hover:border-yellow-500/80 hover:bg-yellow-900/30',
    dot: 'bg-yellow-400',
    badge: 'bg-yellow-900/60 text-yellow-400',
    glow: 'shadow-yellow-900/30',
  },
  slump: {
    card: 'border-red-700/60 bg-red-950/30 hover:border-red-500/80 hover:bg-red-900/30',
    dot: 'bg-red-400',
    badge: 'bg-red-900/60 text-red-400',
    glow: 'shadow-red-900/30',
  },
}

const signalLabel: Record<SignalType, string> = {
  boom: '호황',
  normal: '보통',
  slump: '침체',
}

interface RegionCardProps {
  code: string
  name: string
  emoji: string
  signal?: SignalType
  confidence?: number
  summary?: string
}

function RegionCard({ code, name, emoji, signal, confidence, summary }: RegionCardProps) {
  const navigate = useNavigate()
  const hasData = signal !== undefined
  const styles = signal ? signalStyles[signal] : null

  return (
    <button
      onClick={() => navigate(`/region/${code}`)}
      className={`group relative rounded-2xl border p-4 text-left transition-all duration-200 card-hover shadow-lg ${
        styles
          ? `${styles.card} ${styles.glow}`
          : 'border-slate-700/50 bg-slate-800/50 hover:border-slate-600/80 hover:bg-slate-700/50'
      }`}
    >
      {/* Signal dot pulse */}
      {hasData && signal && (
        <span className="absolute right-3 top-3 flex h-2.5 w-2.5">
          <span
            className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${signalStyles[signal].dot}`}
          />
          <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${signalStyles[signal].dot}`} />
        </span>
      )}

      <div className="mb-2 text-2xl">{emoji}</div>

      <div className="font-bold text-slate-100 text-base">{name}</div>

      {hasData && signal ? (
        <>
          <div
            className={`mt-1.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${styles?.badge}`}
          >
            {signalLabel[signal]}
          </div>
          {confidence !== undefined && (
            <div className="mt-2">
              <div className="h-1 w-full rounded-full bg-slate-700/60">
                <div
                  className={`h-full rounded-full ${styles?.dot}`}
                  style={{ width: `${confidence}%`, opacity: 0.7 }}
                />
              </div>
              <p className="mt-0.5 text-[10px] text-slate-500">{confidence}% 신뢰도</p>
            </div>
          )}
          {summary && (
            <p className="mt-2 line-clamp-2 text-xs text-slate-400 leading-relaxed">{summary}</p>
          )}
        </>
      ) : (
        <div className="mt-2 text-xs text-slate-500">데이터 로딩 중...</div>
      )}
    </button>
  )
}

interface RegionMapProps {
  signals?: RegionSignal[]
  isLoading?: boolean
}

export default function RegionMap({ signals, isLoading }: RegionMapProps) {
  const signalMap = new Map(signals?.map((s) => [s.region_code, s]))

  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5">
      {FIXED_REGIONS.map(({ code, name, emoji }) => {
        const data = signalMap.get(code)
        return (
          <RegionCard
            key={code}
            code={code}
            name={name}
            emoji={emoji}
            signal={isLoading ? undefined : data?.signal}
            confidence={data?.confidence}
            summary={data?.summary}
          />
        )
      })}
    </div>
  )
}
