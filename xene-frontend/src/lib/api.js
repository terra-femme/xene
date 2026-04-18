import { MOCK_FEED, MOCK_ARTISTS } from './mockData'

const API_URL = import.meta.env.VITE_API_URL
const SIMULATED_DELAY_MS = 400

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// Artist config — maps display artists to their real platform identities.
// In Milestone 3 this comes from Supabase (user's saved artist list).
// For now it's hardcoded so the feed works without a DB.
// ---------------------------------------------------------------------------
const ARTIST_CONFIG = [
  { name: 'Call Super',      sc: 'call-super',      bc_url: null, bc_name: null, twitch_login: null, bp_name: 'Call Super',      bp_id: null },
  { name: 'DJ Seinfeld',     sc: 'djseinfeld',      bc_url: null, bc_name: null, twitch_login: null, bp_name: 'DJ Seinfeld',     bp_id: null },
  { name: 'Floating Points', sc: 'floating-points', bc_url: 'https://floatingpoints.bandcamp.com', bc_name: 'Floating Points', twitch_login: null, bp_name: 'Floating Points', bp_id: null },
]

// ---------------------------------------------------------------------------
// fetchFeed
// ---------------------------------------------------------------------------
export async function fetchFeed({ artistId = null } = {}) {
  if (!API_URL) {
    // No backend configured — return mock data for local UI development
    await delay(SIMULATED_DELAY_MS)
    if (!artistId) return MOCK_FEED
    const nameMap = { objekt: 'Objekt', shackleton: 'Shackleton', callsuper: 'Call Super' }
    return MOCK_FEED.filter(item => item.artist_name === nameMap[artistId])
  }

  const config = artistId
    ? ARTIST_CONFIG.filter(a => a.sc === artistId || a.name.toLowerCase().replace(' ', '') === artistId)
    : ARTIST_CONFIG

  const scUsernames = config.map(a => a.sc).filter(Boolean)
  const bcUrls = config.filter(a => a.bc_url).map(a => a.bc_url)
  const bcNames = config.filter(a => a.bc_url).map(a => a.bc_name)

  const params = new URLSearchParams()
  scUsernames.forEach(u => params.append('sc', u))
  bcUrls.forEach(u => params.append('bc_url', u))
  bcNames.forEach(n => params.append('bc_name', n))

  const resp = await fetch(`${API_URL}/feed/merged?${params.toString()}`)
  if (!resp.ok) throw new Error(`Feed fetch failed: ${resp.status}`)
  return resp.json()
}

// ---------------------------------------------------------------------------
// fetchArtists
// ---------------------------------------------------------------------------
export async function fetchArtists() {
  if (!API_URL) {
    await delay(SIMULATED_DELAY_MS / 2)
    return MOCK_ARTISTS
  }
  // In Milestone 3 this hits GET /artists with X-User-Id header (Supabase auth)
  // For now, derive the artist list from ARTIST_CONFIG
  return ARTIST_CONFIG.map((a, i) => ({
    id: a.sc || String(i),
    name: a.name,
    twitch_login: a.twitch_login ?? null,
    beatport_artist_name: a.bp_name ?? null,
    beatport_artist_id: a.bp_id ?? null,
    platforms: [
      a.sc ? 'soundcloud' : null,
      a.bc_url ? 'bandcamp' : null,
      a.bp_name ? 'beatport' : null,
    ].filter(Boolean),
  }))
}

// ---------------------------------------------------------------------------
// fetchArtistDetail
// ---------------------------------------------------------------------------
export async function fetchArtistDetail(artistId) {
  if (!API_URL) {
    await delay(SIMULATED_DELAY_MS)
    const nameMap = { objekt: 'Objekt', shackleton: 'Shackleton', callsuper: 'Call Super' }
    const artist = MOCK_ARTISTS.find(a => a.id === artistId)
    const feed = MOCK_FEED.filter(item => item.artist_name === nameMap[artistId])
    return { artist, feed }
  }

  const [artistsData, feedData] = await Promise.all([
    fetchArtists(),
    fetchFeed({ artistId }),
  ])
  const artist = artistsData.find(a => a.id === artistId)
  return { artist, feed: feedData }
}

// ---------------------------------------------------------------------------
// fetchOembed — get SoundCloud iframe HTML for a track URL
// ---------------------------------------------------------------------------
export async function fetchOembed(trackUrl) {
  if (!API_URL) return null
  const resp = await fetch(`${API_URL}/feed/oembed?url=${encodeURIComponent(trackUrl)}`)
  if (!resp.ok) return null
  return resp.json()
}

// ---------------------------------------------------------------------------
// fetchTwitchStatus — check which of the given Twitch logins are live
// Returns array of TwitchStream objects (only live channels included)
// ---------------------------------------------------------------------------
export async function fetchTwitchStatus(logins) {
  const active = logins.filter(Boolean)
  if (!active.length || !API_URL) {
    console.log('[api] fetchTwitchStatus skipped — no logins or no API_URL', { active, API_URL })
    return []
  }
  console.log('[api] fetchTwitchStatus logins=', active)
  const params = new URLSearchParams()
  active.forEach(login => params.append('logins', login))
  const resp = await fetch(`${API_URL}/twitch/live?${params.toString()}`)
  if (!resp.ok) {
    console.log('[api] fetchTwitchStatus error status=', resp.status)
    return []
  }
  const data = await resp.json()
  console.log('[api] fetchTwitchStatus result count=', data.length, data)
  return data
}
