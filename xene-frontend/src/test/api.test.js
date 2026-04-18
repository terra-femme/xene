// Tests for src/lib/api.js
// Uses fake timers to eliminate the artificial delay without touching the source.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchFeed, fetchArtists, fetchArtistDetail } from '../lib/api'
import { MOCK_FEED, MOCK_ARTISTS } from '../lib/mockData'

// ── fetchFeed ────────────────────────────────────────────────────────────────

describe('fetchFeed', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('returns the full feed when called with no arguments', async () => {
    const promise = fetchFeed()
    vi.runAllTimers()
    const result = await promise
    expect(result).toEqual(MOCK_FEED)
  })

  it('returns the full feed when artistId is null', async () => {
    const promise = fetchFeed({ artistId: null })
    vi.runAllTimers()
    const result = await promise
    expect(result).toEqual(MOCK_FEED)
  })

  it('filters to only Objekt items when artistId="objekt"', async () => {
    const promise = fetchFeed({ artistId: 'objekt' })
    vi.runAllTimers()
    const result = await promise
    expect(result.length).toBeGreaterThan(0)
    expect(result.every(item => item.artist_name === 'Objekt')).toBe(true)
  })

  it('filters to only Shackleton items when artistId="shackleton"', async () => {
    const promise = fetchFeed({ artistId: 'shackleton' })
    vi.runAllTimers()
    const result = await promise
    expect(result.length).toBeGreaterThan(0)
    expect(result.every(item => item.artist_name === 'Shackleton')).toBe(true)
  })

  it('filters to only Call Super items when artistId="callsuper"', async () => {
    const promise = fetchFeed({ artistId: 'callsuper' })
    vi.runAllTimers()
    const result = await promise
    expect(result.length).toBeGreaterThan(0)
    expect(result.every(item => item.artist_name === 'Call Super')).toBe(true)
  })

  it('returns empty array for an unknown artistId', async () => {
    const promise = fetchFeed({ artistId: 'nobody' })
    vi.runAllTimers()
    const result = await promise
    expect(result).toEqual([])
  })
})

// ── fetchArtists ─────────────────────────────────────────────────────────────

describe('fetchArtists', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('returns the MOCK_ARTISTS array', async () => {
    const promise = fetchArtists()
    vi.runAllTimers()
    const result = await promise
    expect(result).toEqual(MOCK_ARTISTS)
  })

  it('returns exactly 3 artists', async () => {
    const promise = fetchArtists()
    vi.runAllTimers()
    const result = await promise
    expect(result).toHaveLength(3)
  })

  it('each artist has id, name, and platforms fields', async () => {
    const promise = fetchArtists()
    vi.runAllTimers()
    const result = await promise
    for (const artist of result) {
      expect(artist).toHaveProperty('id')
      expect(artist).toHaveProperty('name')
      expect(artist).toHaveProperty('platforms')
      expect(Array.isArray(artist.platforms)).toBe(true)
    }
  })
})

// ── fetchArtistDetail ─────────────────────────────────────────────────────────

describe('fetchArtistDetail', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('returns artist metadata for "objekt"', async () => {
    const promise = fetchArtistDetail('objekt')
    vi.runAllTimers()
    const { artist } = await promise
    expect(artist.id).toBe('objekt')
    expect(artist.name).toBe('Objekt')
  })

  it('returns only Objekt feed items for "objekt"', async () => {
    const promise = fetchArtistDetail('objekt')
    vi.runAllTimers()
    const { feed } = await promise
    expect(feed.length).toBeGreaterThan(0)
    expect(feed.every(i => i.artist_name === 'Objekt')).toBe(true)
  })

  it('returns artist metadata for "shackleton"', async () => {
    const promise = fetchArtistDetail('shackleton')
    vi.runAllTimers()
    const { artist } = await promise
    expect(artist.id).toBe('shackleton')
    expect(artist.name).toBe('Shackleton')
  })

  it('returns undefined artist for an unknown id', async () => {
    const promise = fetchArtistDetail('nobody')
    vi.runAllTimers()
    const { artist, feed } = await promise
    expect(artist).toBeUndefined()
    expect(feed).toEqual([])
  })
})
