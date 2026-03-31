import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="mx-auto mt-16 max-w-xl rounded-2xl border border-slate-700/50 bg-slate-800/60 p-8 text-center">
      <h1 className="text-3xl font-bold text-slate-100">404</h1>
      <p className="mt-2 text-sm text-slate-400">요청한 페이지를 찾을 수 없습니다.</p>
      <Link
        to="/"
        className="mt-6 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        대시보드로 이동
      </Link>
    </div>
  )
}

