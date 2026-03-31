import Dashboard from '@/pages/Dashboard'
import { server } from '@/test/setup'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Dashboard', () => {
  it('renders overview data from API', async () => {
    server.use(
      http.get('*/api/v1/economy/overview', () =>
        HttpResponse.json({
          regions: [
            {
              region_code: 'seoul',
              region_name: '서울',
              signal: 'boom',
              confidence: 83,
              summary: '상승 탄력 유지',
              indicators: [],
            },
            {
              region_code: 'busan',
              region_name: '부산',
              signal: 'slump',
              confidence: 62,
              summary: '매물 누적 증가',
              indicators: [],
            },
          ],
        })
      ),
    )

    renderDashboard()

    expect(await screen.findByText('부동산 경제 대시보드')).toBeInTheDocument()
    expect(await screen.findByText('서울')).toBeInTheDocument()
    expect(await screen.findByText(/신뢰도 83%/)).toBeInTheDocument()
  })
})

