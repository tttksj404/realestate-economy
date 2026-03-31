import ErrorBoundary from '@/components/ErrorBoundary'
import { LayoutDashboard, MapPin, MessageSquare, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Chat from '@/pages/Chat'
import Dashboard from '@/pages/Dashboard'
import NotFound from '@/pages/NotFound'
import RegionDetail from '@/pages/RegionDetail'

const regions = [
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

function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <aside className={`border-r border-slate-700/50 bg-slate-900/90 ${collapsed ? 'w-16' : 'w-60'} transition-all`}>
      <div className="flex h-16 items-center gap-2 border-b border-slate-700/50 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
          <TrendingUp size={16} className="text-white" />
        </div>
        {!collapsed && <span className="text-sm font-semibold text-slate-200">부동산 경제 분석</span>}
      </div>

      <nav className="space-y-1 p-2">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
              isActive ? 'bg-blue-600/20 text-blue-300' : 'text-slate-400 hover:bg-slate-800/70'
            }`
          }
        >
          <LayoutDashboard size={16} />
          {!collapsed && '대시보드'}
        </NavLink>
        <NavLink
          to="/chat"
          className={({ isActive }) =>
            `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
              isActive ? 'bg-blue-600/20 text-blue-300' : 'text-slate-400 hover:bg-slate-800/70'
            }`
          }
        >
          <MessageSquare size={16} />
          {!collapsed && 'AI 채팅'}
        </NavLink>
      </nav>

      {!collapsed && (
        <div className="border-t border-slate-700/50 p-2">
          <p className="px-3 pb-2 text-[11px] text-slate-500">지역</p>
          <div className="space-y-1">
            {regions.map((region) => (
              <NavLink
                key={region.code}
                to={`/region/${region.code}`}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${
                    isActive ? 'bg-slate-700/80 text-slate-100' : 'text-slate-400 hover:bg-slate-800/70'
                  }`
                }
              >
                <MapPin size={12} />
                {region.name}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <ErrorBoundary>
      <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
        <Sidebar collapsed={collapsed} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b border-slate-700/50 bg-slate-900/70 px-4 sm:px-6">
            <p className="text-sm text-slate-400">
              {location.pathname === '/' && '전국 부동산 경제 요약'}
              {location.pathname === '/chat' && 'AI 기반 매물/거시경제 질의'}
              {location.pathname.startsWith('/region/') && '지역 상세 분석'}
            </p>
            <button
              onClick={() => setCollapsed((prev) => !prev)}
              className="rounded-lg border border-slate-700/60 px-2 py-1 text-xs text-slate-300"
            >
              {collapsed ? '펼치기' : '접기'}
            </button>
          </header>

          <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/region/:code" element={<RegionDetail />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
        </div>
      </div>
    </ErrorBoundary>
  )
}

