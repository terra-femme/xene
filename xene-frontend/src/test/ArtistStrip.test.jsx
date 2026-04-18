// Tests for src/components/ArtistStrip.jsx
// framer-motion is mocked so motion.button renders as a plain <button>.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ArtistStrip from '../components/ArtistStrip'

vi.mock('framer-motion', () => ({
  motion: {
    button: ({ children, onClick, className }) =>
      <button onClick={onClick} className={className}>{children}</button>,
    span: ({ children }) => <span>{children}</span>,
  },
  AnimatePresence: ({ children }) => children,
}))

const MOCK_ARTISTS = [
  { id: 'objekt',     name: 'Objekt',     platforms: ['soundcloud', 'bandcamp'] },
  { id: 'shackleton', name: 'Shackleton', platforms: ['bandcamp'] },
]

describe('ArtistStrip — pill rendering', () => {
  it('always renders the "All" pill', () => {
    render(<ArtistStrip artists={MOCK_ARTISTS} selected={null} onSelect={() => {}} />)
    expect(screen.getByText('All')).toBeInTheDocument()
  })

  it('renders one pill per artist', () => {
    render(<ArtistStrip artists={MOCK_ARTISTS} selected={null} onSelect={() => {}} />)
    expect(screen.getByText('Objekt')).toBeInTheDocument()
    expect(screen.getByText('Shackleton')).toBeInTheDocument()
  })

  it('renders with an empty artists array — only "All" pill present', () => {
    render(<ArtistStrip artists={[]} selected={null} onSelect={() => {}} />)
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(1)
  })
})

describe('ArtistStrip — selection callbacks', () => {
  it('calls onSelect(null) when "All" is clicked', () => {
    const onSelect = vi.fn()
    render(<ArtistStrip artists={MOCK_ARTISTS} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('All'))
    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('calls onSelect with the artist id when an artist pill is clicked', () => {
    const onSelect = vi.fn()
    render(<ArtistStrip artists={MOCK_ARTISTS} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Objekt'))
    expect(onSelect).toHaveBeenCalledWith('objekt')
  })

  it('calls onSelect with the correct id for a different artist', () => {
    const onSelect = vi.fn()
    render(<ArtistStrip artists={MOCK_ARTISTS} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Shackleton'))
    expect(onSelect).toHaveBeenCalledWith('shackleton')
  })
})

describe('ArtistStrip — active state', () => {
  it('applies gold styling to the active artist pill', () => {
    render(<ArtistStrip artists={MOCK_ARTISTS} selected="objekt" onSelect={() => {}} />)
    const objektBtn = screen.getByText('Objekt').closest('button')
    expect(objektBtn.className).toContain('border-xene-gold')
  })

  it('does not apply gold styling to inactive pills', () => {
    render(<ArtistStrip artists={MOCK_ARTISTS} selected="objekt" onSelect={() => {}} />)
    const shackBtn = screen.getByText('Shackleton').closest('button')
    expect(shackBtn.className).not.toContain('border-xene-gold')
  })
})
