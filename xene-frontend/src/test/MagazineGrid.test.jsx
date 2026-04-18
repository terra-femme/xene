// Tests for src/components/MagazineGrid.jsx
// ArtistCard is stubbed so this test focuses only on MagazineGrid's own logic:
// — skeleton while loading
// — empty state message
// — correct number of cards rendered
// — newest-first sort order

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import MagazineGrid from '../components/MagazineGrid'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children }) => <div>{children}</div>,
  },
  AnimatePresence: ({ children }) => children,
}))

// Stub ArtistCard to expose just enough for assertions
vi.mock('../components/ArtistCard', () => ({
  default: ({ item }) => <div data-testid="artist-card">{item.title ?? item.artist_name}</div>,
}))

const makeItem = (id, title, published_at) => ({
  id,
  title,
  artist_name: 'Test Artist',
  published_at,
})

describe('MagazineGrid — loading state', () => {
  it('renders a skeleton grid when loading=true', () => {
    const { container } = render(<MagazineGrid items={[]} loading={true} />)
    // Skeleton produces a grid container
    expect(container.querySelector('.grid')).toBeInTheDocument()
    // No real cards in skeleton
    expect(screen.queryAllByTestId('artist-card')).toHaveLength(0)
  })
})

describe('MagazineGrid — empty state', () => {
  it('shows "No items" when items is an empty array and not loading', () => {
    render(<MagazineGrid items={[]} loading={false} />)
    expect(screen.getByText('No items')).toBeInTheDocument()
  })

  it('shows "No items" when items is null and not loading', () => {
    render(<MagazineGrid items={null} loading={false} />)
    expect(screen.getByText('No items')).toBeInTheDocument()
  })
})

describe('MagazineGrid — item rendering', () => {
  it('renders one card per item', () => {
    const items = [
      makeItem('1', 'Track Alpha', '2026-04-10T00:00:00Z'),
      makeItem('2', 'Track Beta',  '2026-04-09T00:00:00Z'),
      makeItem('3', 'Track Gamma', '2026-04-08T00:00:00Z'),
    ]
    render(<MagazineGrid items={items} loading={false} />)
    expect(screen.getAllByTestId('artist-card')).toHaveLength(3)
  })

  it('sorts items newest-first regardless of input order', () => {
    const items = [
      makeItem('old', 'Oldest',  '2026-03-01T00:00:00Z'),
      makeItem('new', 'Newest',  '2026-04-10T00:00:00Z'),
      makeItem('mid', 'Middle',  '2026-04-01T00:00:00Z'),
    ]
    render(<MagazineGrid items={items} loading={false} />)
    const cards = screen.getAllByTestId('artist-card')
    expect(cards[0].textContent).toBe('Newest')
    expect(cards[1].textContent).toBe('Middle')
    expect(cards[2].textContent).toBe('Oldest')
  })

  it('does not mutate the input items array', () => {
    const items = [
      makeItem('a', 'A', '2026-04-01T00:00:00Z'),
      makeItem('b', 'B', '2026-04-10T00:00:00Z'),
    ]
    const originalOrder = items.map(i => i.id)
    render(<MagazineGrid items={items} loading={false} />)
    expect(items.map(i => i.id)).toEqual(originalOrder)
  })
})
