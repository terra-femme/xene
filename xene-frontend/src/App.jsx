import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Feed from './pages/Feed'
import ArtistDetail from './pages/ArtistDetail'
import InstallPrompt from './components/InstallPrompt'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/artist/:artistId" element={<ArtistDetail />} />
        </Routes>
        <InstallPrompt />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
