import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react'
import { Send, Trash2, Bot, Sparkles } from 'lucide-react'
import { useChat } from '@/hooks/useChat'
import ChatMessage, { LoadingDots } from '@/components/ChatMessage'

const SUGGESTED_QUESTIONS = [
  '서울 아파트 시장 현황을 알려줘',
  '경기도 부동산 투자 전망은?',
  '현재 가장 호황인 지역은 어디야?',
  '부산 오피스텔 매물 동향 분석해줘',
  '전국 부동산 시장 요약해줘',
  '금리 변화가 부동산 시장에 미치는 영향은?',
]

export default function Chat() {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return
    setInput('')
    await sendMessage(text)
    inputRef.current?.focus()
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  function handleSuggestedQuestion(q: string) {
    if (isLoading) return
    setInput('')
    void sendMessage(q)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700/50 pb-4 mb-0">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600/20 border border-blue-500/30">
            <Bot size={18} className="text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100">AI 부동산 분석</h1>
            <p className="text-xs text-slate-500">부동산 시장 데이터 기반 AI 상담</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-800/60 px-3 py-2 text-xs text-slate-400 hover:text-red-400 hover:border-red-800/50 hover:bg-red-950/20 transition-all"
          >
            <Trash2 size={13} />
            대화 초기화
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-10 space-y-6 animate-fade-in">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600/10 border border-blue-500/20">
              <Sparkles size={28} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-200">부동산 AI 어시스턴트</h2>
              <p className="mt-1 text-sm text-slate-500 max-w-sm">
                지역별 부동산 시장 현황, 가격 동향, 매물 정보를<br />
                실시간 데이터 기반으로 분석해 드립니다.
              </p>
            </div>

            <div className="w-full max-w-lg">
              <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-600">추천 질문</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSuggestedQuestion(q)}
                    className="rounded-xl border border-slate-700/50 bg-slate-800/60 px-3 py-2 text-xs text-slate-400 hover:text-slate-200 hover:border-blue-600/50 hover:bg-blue-950/30 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isLoading && messages[messages.length - 1]?.role === 'user' && (
              <LoadingDots />
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-0 mb-2 rounded-xl border border-red-800/50 bg-red-950/30 px-4 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Suggested chips (when there are messages) */}
      {messages.length > 0 && !isLoading && (
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {SUGGESTED_QUESTIONS.slice(0, 3).map((q) => (
            <button
              key={q}
              onClick={() => handleSuggestedQuestion(q)}
              className="shrink-0 rounded-full border border-slate-700/50 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:border-blue-600/50 hover:bg-blue-950/20 transition-all"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input form */}
      <div className="border-t border-slate-700/50 pt-4">
        <form onSubmit={(e) => { void handleSubmit(e) }} className="flex gap-3 items-end">
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="부동산 시장에 대해 무엇이든 물어보세요... (Enter로 전송, Shift+Enter 줄바꿈)"
              disabled={isLoading}
              rows={1}
              className="w-full resize-none rounded-2xl border border-slate-700/50 bg-slate-800/80 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-600/60 focus:outline-none focus:ring-1 focus:ring-blue-600/40 disabled:opacity-50 transition-colors"
              style={{ minHeight: '46px', maxHeight: '120px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = `${Math.min(target.scrollHeight, 120)}px`
              }}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
          >
            <Send size={16} />
          </button>
        </form>
        <p className="mt-1.5 text-center text-[10px] text-slate-600">
          AI 분석은 참고용입니다. 실제 투자 결정 시 전문가 상담을 권장합니다.
        </p>
      </div>
    </div>
  )
}
