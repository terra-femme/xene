// Tests for src/components/SoundCloudPlayer.jsx
// framer-motion mocked so AnimatePresence / motion.span render as plain elements.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SoundCloudPlayer from '../components/SoundCloudPlayer'

vi.mock('framer-motion', () => ({
  motion: {
    span: ({ children }) => <span>{children}</span>,
  },
  AnimatePresence: ({ children }) => children,
}))

const TRACK = {
  id: 'obj-sc-001',
  platform: 'soundcloud',
  artist_name: 'Objekt',
  play_count: 84200,
  like_count: 3100,
  waveform_url: 'https://wave.sndcdn.com/fake/objekt1',
}

describe('SoundCloudPlayer — play/pause toggle', () => {
  it('initially shows the Play aria-label', () => {
    render(<SoundCloudPlayer item={TRACK} />)
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
  })

  it('switches to Pause aria-label after one click', () => {
    render(<SoundCloudPlayer item={TRACK} />)
    fireEvent.click(screen.getByRole('button', { name: /play/i }))
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument()
  })

  it('returns to Play aria-label after two clicks', () => {
    render(<SoundCloudPlayer item={TRACK} />)
    const btn = screen.getByRole('button', { name: /play/i })
    fireEvent.click(btn)
    fireEvent.click(screen.getByRole('button', { name: /pause/i }))
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
  })
})

describe('SoundCloudPlayer — metadata display', () => {
  it('shows formatted play count when compact=false', () => {
    render(<SoundCloudPlayer item={TRACK} compact={false} />)
    expect(screen.getByText('84.2k plays')).toBeInTheDocument()
  })

  it('shows formatted like count when compact=false', () => {
    render(<SoundCloudPlayer item={TRACK} compact={false} />)
    expect(screen.getByText('3.1k likes')).toBeInTheDocument()
  })

  it('hides metadata row when compact=true', () => {
    render(<SoundCloudPlayer item={TRACK} compact={true} />)
    expect(screen.queryByText(/plays/)).not.toBeInTheDocument()
    expect(screen.queryByText(/likes/)).not.toBeInTheDocument()
  })

  it('does not render play count when play_count is null', () => {
    render(<SoundCloudPlayer item={{ ...TRACK, play_count: null }} compact={false} />)
    expect(screen.queryByText(/plays/)).not.toBeInTheDocument()
  })

  it('does not render like count when like_count is null', () => {
    render(<SoundCloudPlayer item={{ ...TRACK, like_count: null }} compact={false} />)
    expect(screen.queryByText(/likes/)).not.toBeInTheDocument()
  })

  it('formats counts under 1000 without a "k" suffix', () => {
    render(<SoundCloudPlayer item={{ ...TRACK, play_count: 500, like_count: 42 }} compact={false} />)
    expect(screen.getByText('500 plays')).toBeInTheDocument()
    expect(screen.getByText('42 likes')).toBeInTheDocument()
  })
})
