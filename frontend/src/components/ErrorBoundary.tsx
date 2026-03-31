import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    message: '',
  }

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message }
  }

  public componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught an error', error, info)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto max-w-2xl rounded-2xl border border-red-800/50 bg-red-950/30 p-6 text-red-100">
          <h2 className="text-lg font-semibold">화면 렌더링 중 오류가 발생했습니다.</h2>
          <p className="mt-2 text-sm text-red-200/80">{this.state.message}</p>
        </div>
      )
    }

    return this.props.children
  }
}

