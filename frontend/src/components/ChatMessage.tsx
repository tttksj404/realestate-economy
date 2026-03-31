import type { ChatMessage as ChatMessageType } from '@/types'
import { Bot, User } from 'lucide-react'
import type { ReactNode } from 'react'

interface ChatMessageProps {
  message: ChatMessageType
}

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={`${part}-${index}`} className="rounded bg-slate-700 px-1 py-0.5 text-xs text-blue-200">
          {part.slice(1, -1)}
        </code>
      )
    }

    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={`${part}-${index}`} className="font-semibold text-slate-50">
          {part.slice(2, -2)}
        </strong>
      )
    }

    return <span key={`${part}-${index}`}>{part}</span>
  })
}

function MarkdownLikeContent({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  const lines = content.split('\n')
  let inCodeBlock = false
  const codeBuffer: string[] = []
  const elements: ReactNode[] = []

  function flushCodeBlock(key: string) {
    if (codeBuffer.length === 0) {
      return
    }

    elements.push(
      <pre key={key} className="overflow-x-auto rounded-lg bg-slate-900/80 p-3 text-xs text-slate-200">
        <code>{codeBuffer.join('\n')}</code>
      </pre>
    )
    codeBuffer.length = 0
  }

  lines.forEach((line, index) => {
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        flushCodeBlock(`code-${index}`)
      }
      inCodeBlock = !inCodeBlock
      return
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      return
    }

    if (line.startsWith('- ')) {
      elements.push(
        <li key={`li-${index}`} className="ml-4 list-disc text-sm leading-relaxed text-slate-200">
          {renderInline(line.slice(2))}
        </li>
      )
      return
    }

    elements.push(
      <p key={`p-${index}`} className="text-sm leading-relaxed text-slate-200">
        {renderInline(line)}
      </p>
    )
  })

  if (inCodeBlock) {
    flushCodeBlock('code-last')
  }

  return (
    <div className="space-y-1.5">
      {elements}
      {isStreaming && <span className="inline-block h-4 w-0.5 animate-pulse bg-blue-400 align-middle" />}
    </div>
  )
}

export function LoadingDots() {
  return (
    <div className="flex items-center gap-1">
      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.2s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.1s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
    </div>
  )
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-200'
        }`}
      >
        {isUser ? <User size={15} /> : <Bot size={15} />}
      </div>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? 'rounded-tr-sm bg-blue-600 text-white' : 'rounded-tl-sm bg-slate-700/80'
        }`}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed">{message.content}</p>
        ) : message.content ? (
          <MarkdownLikeContent content={message.content} isStreaming={message.isStreaming} />
        ) : (
          <LoadingDots />
        )}
      </div>
    </div>
  )
}

