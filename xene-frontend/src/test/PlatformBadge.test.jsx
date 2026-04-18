// Tests for src/components/PlatformBadge.jsx
// Pure presentational component — no mocks needed.

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PlatformBadge from '../components/PlatformBadge'

describe('PlatformBadge — known platforms', () => {
  it('renders "SC" for soundcloud', () => {
    render(<PlatformBadge platform="soundcloud" />)
    expect(screen.getByText('SC')).toBeInTheDocument()
  })

  it('renders "IG" for instagram', () => {
    render(<PlatformBadge platform="instagram" />)
    expect(screen.getByText('IG')).toBeInTheDocument()
  })

  it('renders "BC" for bandcamp', () => {
    render(<PlatformBadge platform="bandcamp" />)
    expect(screen.getByText('BC')).toBeInTheDocument()
  })

  it('renders "BP" for beatport', () => {
    render(<PlatformBadge platform="beatport" />)
    expect(screen.getByText('BP')).toBeInTheDocument()
  })

  it('renders "TT" for tiktok', () => {
    render(<PlatformBadge platform="tiktok" />)
    expect(screen.getByText('TT')).toBeInTheDocument()
  })
})

describe('PlatformBadge — unknown platform fallback', () => {
  it('renders the platform name uppercased when platform is unrecognised', () => {
    render(<PlatformBadge platform="myspace" />)
    expect(screen.getByText('MYSPACE')).toBeInTheDocument()
  })

  it('falls back to a neutral grey color for unknown platforms', () => {
    const { container } = render(<PlatformBadge platform="myspace" />)
    // The span's inline color should be the fallback #888
    expect(container.firstChild.style.color).toBe('rgb(136, 136, 136)')
  })
})

describe('PlatformBadge — size prop', () => {
  it('uses small text class by default (size="sm")', () => {
    const { container } = render(<PlatformBadge platform="soundcloud" />)
    expect(container.firstChild.className).toContain('text-[10px]')
  })

  it('uses larger text class when size="lg"', () => {
    const { container } = render(<PlatformBadge platform="soundcloud" size="lg" />)
    expect(container.firstChild.className).toContain('text-xs')
  })
})
