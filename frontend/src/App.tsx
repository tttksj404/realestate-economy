import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, MessageSquare, MapPin, TrendingUp, Menu, X } from 'lucide-react'
import { useState } from 'react'
import Dashboard from '@/pages/Dashboard'
import RegionDetail from '@/pages/RegionDetail'
import Chat from '@/pages/Chat'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: '대시보드', end: true },
  { to: '/chat', icon: MessageSquare, label: 'AI 상담' },
] as const

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={`flex flex-col border-r border-slate-700/50 bg-slate-900/95 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-slate-700/50 shrink-0">
        {!collapsed && (
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-600">
              <TrendingUp size={14} className="text-white" />
            </div>
            <span className="truncate text-sm font-bold text-slate-100">부동산 분석</span>
          </div>
        )}
        {collapsed && (
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 mx-auto">
            <TrendingUp size={14} className="text-white" />
          </div>
        )}
        {!collapsed && (
          <button
            onClick={onToggle}
            className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600/20 border border-blue-600/30 text-blue-400'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              } ${collapsed ? 'justify-center' : ''}`
            }
            title={collapsed ? label : undefined}
          >
            <Icon size={16} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}

        {!collapsed && (
          <div className="pt-4">
            <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600 mb-2">
              지역
            </p>
            {[
              { code: 'seoul', name: '서울' },
              { code: 'gyeonggi', name: '경기' },
              { code: 'incheon', name: '인천' },
              { code: 'busan', name: '부산' },
              { code: 'daegu', name: '대구' },
              { code: 'daejeon', name: '대전' },
              { code: 'gwangju', name: '광주' },
              { code: 'ulsan', name: '울산' },
              { code: 'sejong', name: '세종' },
            ].map(({ code, name }) => (
              <NavLink
                key={code}
                to={`/region/${code}`}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors ${
                    isActive
                      ? 'bg-slate-700/60 text-slate-200'
                      : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40'
                  }`
                }
              >
                <MapPin size={11} className="shrink-0" />
                {name}
              </NavLink>
            ))}
          </div>
        )}
      </nav>

      {/* Collapse toggle at bottom */}
      {collapsed && (
        <div className="p-2 border-t border-slate-700/50">
          <button
            onClick={onToggle}
            className="flex w-full items-center justify-center rounded-xl p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 transition-colors"
          >
            <Menu size={16} />
          </button>
        </div>
      )}
    </aside>
  )
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const isChat = location.pathname === '/chat'

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((v) => !v)} />

      <main className={`flex flex-1 flex-col overflow-hidden ${isChat ? '' : ''}`}>
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-700/50 bg-slate-900/60 px-6">
          <div className="text-sm text-slate-500">
            {location.pathname === '/' && '전국 부동산 시장 현황'}
            {location.pathname === '/chat' && 'AI 부동산 분석 상담'}
            {location.pathname.startsWith('/region/') && '지역 상세 분석'}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            실시간 데이터
          </div>
        </header>

        {/* Page content */}
        <div className={`flex-1 overflow-y-auto ${isChat ? 'flex flex-col' : ''}`}>
          <div className={`mx-auto w-full max-w-6xl ${isChat ? 'flex flex-1 flex-col h-full px-6 py-5' : 'px-6 py-6'}`}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/region/:code" element={<RegionDetail />} />
              <Route path="/chat" element={<Chat />} />
            </Routes>
          </div>
        </div>
      </main>
    </div>
  )
}
