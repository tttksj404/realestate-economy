import ChatMessage, { LoadingDots } from '@/components/ChatMessage'
import { useChat } from '@/hooks/useChat'
import { Bot, Send, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

const SUGGESTED_QUESTIONS = [
  '서울 아파트 시장 상황을 요약해줘',
  '경기 지역이 침체 신호인지 알려줘',
  '전세가율이 높은 지역을 설명해줘',
  '최근 매물 증가가 큰 지역은 어디야?',
]

export default function Chat() {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChat()
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(event?: FormEvent) {
    event?.preventDefault()
    const text = input.trim()
    if (!text || isLoading) {
      return
    }

    setInput('')
    await sendMessage(text)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSubmit()
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between border-b border-slate-700/50 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600/20 text-blue-300">
            <Bot size={18} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-100">AI 부동산 분석 채팅</h1>
            <p className="text-xs text-slate-500">SSE 스트리밍 응답</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700/60 px-3 py-1.5 text-xs text-slate-300"
          >
            <Trash2 size={12} />
            초기화
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-700/50 bg-slate-900/30 p-4">
        {messages.length === 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">추천 질문을 눌러 바로 시작할 수 있습니다.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  key={question}
                  onClick={() => {
                    void sendMessage(question)
                  }}
                  disabled={isLoading}
                  className="rounded-full border border-slate-700/60 bg-slate-800/70 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => <ChatMessage key={message.id} message={message} />)
        )}
        {isLoading && messages[messages.length - 1]?.role === 'user' && <LoadingDots />}
        <div ref={endRef} />
      </div>

      {messages.length > 0 && !isLoading && (
        <div className="mt-2 flex gap-2 overflow-x-auto">
          {SUGGESTED_QUESTIONS.slice(0, 3).map((question) => (
            <button
              key={`chip-${question}`}
              onClick={() => {
                void sendMessage(question)
              }}
              className="shrink-0 rounded-full border border-slate-700/60 px-3 py-1 text-xs text-slate-300"
            >
              {question}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-2 rounded-lg bg-red-950/30 px-3 py-2 text-xs text-red-300">{error}</p>}

      <form onSubmit={(event) => void handleSubmit(event)} className="mt-4 flex items-end gap-2">
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="질문을 입력하세요. Enter 전송 / Shift+Enter 줄바꿈"
          className="max-h-36 min-h-[46px] flex-1 resize-none rounded-xl border border-slate-700/60 bg-slate-800/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500/70"
          disabled={isLoading}
        />
        <button
          aria-label="메시지 전송"
          type="submit"
          disabled={isLoading || !input.trim()}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600 text-white disabled:opacity-50"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  )
}


