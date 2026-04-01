import { streamChat } from '@/api/client'
import type { ChatMessage } from '@/types'
import { useCallback, useRef, useState } from 'react'

function makeId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef(false)
  const messagesRef = useRef<ChatMessage[]>([])

  const syncMessages = useCallback((updater: (prev: ChatMessage[]) => ChatMessage[]) => {
    setMessages((prev) => {
      const next = updater(prev)
      messagesRef.current = next
      return next
    })
  }, [])

  const sendMessage = useCallback(
    async (content: string, region?: string) => {
      const trimmed = content.trim()
      if (!trimmed || isLoading) {
        return
      }

      setError(null)
      abortRef.current = false

      const userMessage: ChatMessage = {
        id: makeId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      }

      const assistantId = makeId()
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      }

      syncMessages((prev) => [...prev, userMessage, assistantMessage])
      setIsLoading(true)

      const history = messagesRef.current
        .filter((m) => m.id !== assistantId)
        .map((m) => ({ role: m.role, content: m.content }))

      await streamChat(
        { message: trimmed, region, history },
        (token) => {
          if (abortRef.current) {
            return
          }
          syncMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token.content } : m
            )
          )
        },
        () => {
          syncMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m))
          )
          setIsLoading(false)
        },
        (streamError) => {
          setError(`AI 응답 오류: ${streamError.message}`)
          syncMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: '응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
                    isStreaming: false,
                  }
                : m
            )
          )
          setIsLoading(false)
        }
      )
    },
    [isLoading, syncMessages]
  )

  const clearMessages = useCallback(() => {
    abortRef.current = true
    messagesRef.current = []
    setMessages([])
    setError(null)
    setIsLoading(false)
  }, [])

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  }
}

