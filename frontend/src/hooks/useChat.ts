import { useState, useCallback, useRef } from 'react'
import { streamChat } from '@/api/client'
import type { ChatMessage } from '@/types'

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<boolean>(false)

  const sendMessage = useCallback(async (content: string, region?: string) => {
    if (!content.trim() || isLoading) return

    setError(null)
    abortRef.current = false

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }

    // Add placeholder assistant message
    const assistantId = generateId()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMessage, assistantMessage])
    setIsLoading(true)

    // Build history for context
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    await streamChat(
      { message: content.trim(), region, history },
      (token) => {
        if (abortRef.current) return
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content + token.content }
              : m
          )
        )
      },
      () => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        )
        setIsLoading(false)
      },
      (err) => {
        setError(`AI 응답 오류: ${err.message}`)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: '죄송합니다. 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
                  isStreaming: false,
                }
              : m
          )
        )
        setIsLoading(false)
      }
    )
  }, [messages, isLoading])

  const clearMessages = useCallback(() => {
    abortRef.current = true
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
