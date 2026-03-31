import Chat from '@/pages/Chat'
import { useChat } from '@/hooks/useChat'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

vi.mock('@/hooks/useChat', () => ({
  useChat: vi.fn(),
}))

describe('Chat', () => {
  it('sends message on submit and supports suggested question click', async () => {
    const sendMessage = vi.fn().mockResolvedValue(undefined)
    const clearMessages = vi.fn()

    vi.mocked(useChat).mockReturnValue({
      messages: [],
      isLoading: false,
      error: null,
      sendMessage,
      clearMessages,
    })

    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Chat />
      </MemoryRouter>
    )

    await user.type(screen.getByPlaceholderText(/질문을 입력하세요/), '서울 상황 알려줘')
    await user.click(screen.getByRole('button', { name: '메시지 전송' }))
    expect(sendMessage).toHaveBeenCalledWith('서울 상황 알려줘')

    await user.click(screen.getByRole('button', { name: '서울 아파트 시장 상황을 요약해줘' }))
    expect(sendMessage).toHaveBeenCalledWith('서울 아파트 시장 상황을 요약해줘')
  })
})

