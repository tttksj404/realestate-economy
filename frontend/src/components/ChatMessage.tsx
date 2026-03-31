import type { ReactNode } from 'react'
import type { ChatMessage as ChatMessageType } from '@/types'
import { Bot, User } from 'lucide-react'

interface ChatMessageProps {
  message: ChatMessageType
}

function formatContent(content: string): string[] {
  return content.split('\n').filter((line, idx, arr) => !(line === '' && arr[idx - 1] === ''))
}

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-slate-100">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="rounded bg-slate-700/80 px-1 py-0.5 font-mono text-xs text-blue-300">
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={i}>{part}</span>
  })
}

function MessageContent({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  const lines = formatContent(content)

  if (lines.length === 0) return null

  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith('### ')) {
          return <h4 key={i} className="font-bold text-slate-100 text-sm">{line.slice(4)}</h4>
        }
        if (line.startsWith('## ')) {
          return <h3 key={i} className="font-bold text-slate-100 text-base">{line.slice(3)}</h3>
        }
        if (line.startsWith('# ')) {
          return <h2 key={i} className="font-bold text-slate-100 text-lg">{line.slice(2)}</h2>
        }
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2">
              <span className="mt-1 shrink-0 text-slate-500">•</span>
              <span>{renderInline(line.slice(2))}</span>
            </div>
          )
        }
        if (/^\d+\.\s/.test(line)) {
          const match = line.match(/^(\d+)\.\s(.*)/)
          if (match) {
            return (
              <div key={i} className="flex gap-2">
                <span className="shrink-0 font-semibold text-blue-400">{match[1]}.</span>
                <span>{renderInline(match[2])}</span>
              </div>
            )
          }
        }
        if (line === '') {
          return <div key={i} className="h-1" />
        }
        return <p key={i}>{renderInline(line)}</p>
      })}
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-text-bottom" />
      )}
    </div>
  )
}

export function LoadingDots() {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-slate-400">
        <Bot size={16} />
      </div>
      <div className="rounded-2xl rounded-tl-sm bg-slate-700/80 px-4 py-3">
        <div className="loading-dots flex items-center gap-1">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  )
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex items-start gap-3 flex-row-reverse animate-fade-in">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white">
          <User size={16} />
        </div>
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-blue-600/90 px-4 py-3 text-white">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 animate-fade-in">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-slate-300">
        <Bot size={16} />
      </div>
      <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-slate-700/80 px-4 py-3 text-slate-200">
        {message.content ? (
          <MessageContent content={message.content} isStreaming={message.isStreaming} />
        ) : (
          <LoadingDots />
        )}
        <div className="mt-1.5 text-right text-[10px] text-slate-500">
          {message.timestamp.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}
