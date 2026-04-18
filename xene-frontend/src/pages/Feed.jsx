// Main magazine view — the primary screen of Xene.

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { fetchArtists } from '../lib/api'
import { useFeed } from '../hooks/useFeed'
import { useTwitchStatus } from '../hooks/useTwitchStatus'
import ArtistStrip from '../components/ArtistStrip'
import MagazineGrid from '../components/MagazineGrid'
import TwitchLiveCard from '../components/TwitchLiveCard'

export default function Feed() {
  const [selectedArtist, setSelectedArtist] = useState(null)

  const { data: artists = [] } = useQuery({
    queryKey: ['artists'],
    queryFn: fetchArtists,
    staleTime: 10 * 60 * 1000,
  })

  const { data: feedItems, isLoading } = useFeed(selectedArtist)
  const liveLogins = useTwitchStatus(artists)

  // Streams visible in the current view: all if no filter, else just the selected artist
  const visibleStreams = [...liveLogins.values()].filter(stream => {
    if (!selectedArtist) return true
    const artist = artists.find(a => a.id === selectedArtist)
    return artist?.twitch_login === stream.twitch_login
  })

  return (
    <div className="min-h-screen bg-xene-bg">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-xene-bg/95 backdrop-blur-sm border-b border-xene-border">
        <div className="flex items-center justify-between px-4 py-3">
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className="flex items-baseline gap-3"
          >
            <span className="font-display text-3xl tracking-widest text-xene-text">XENE</span>
            <span className="font-mono text-[10px] text-xene-gold uppercase tracking-widest hidden sm:block">
              your artists / every platform
            </span>
          </motion.div>

          {/* Issue/date badge */}
          <div className="font-mono text-[10px] text-xene-muted uppercase tracking-widest">
            {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toUpperCase()}
          </div>
        </div>

        {/* Artist filter strip */}
        <div className="py-2 border-t border-xene-border">
          <ArtistStrip
            artists={artists}
            selected={selectedArtist}
            onSelect={setSelectedArtist}
            liveLogins={liveLogins}
          />
        </div>
      </header>

      {/* Feed count */}
      {!isLoading && feedItems && (
        <div className="px-4 py-2 border-b border-xene-border">
          <span className="font-mono text-[10px] text-xene-muted uppercase tracking-widest">
            {feedItems.length} item{feedItems.length !== 1 ? 's' : ''}
            {selectedArtist && artists.find(a => a.id === selectedArtist) && (
              <> · {artists.find(a => a.id === selectedArtist).name}</>
            )}
          </span>
        </div>
      )}

      {/* Twitch live cards — shown above feed when any visible artist is streaming */}
      {visibleStreams.length > 0 && (
        <div className="border-b border-xene-border px-4 py-3 flex flex-col gap-2">
          <span className="font-mono text-[9px] uppercase tracking-widest text-[#9146ff]/80">
            Live now
          </span>
          {visibleStreams.map((stream, i) => (
            <TwitchLiveCard key={stream.twitch_login} stream={stream} index={i} />
          ))}
        </div>
      )}

      {/* Magazine grid */}
      <main>
        <MagazineGrid items={feedItems} loading={isLoading} />
      </main>

      {/* Footer */}
      <footer className="border-t border-xene-border px-4 py-6 mt-px">
        <p className="font-mono text-[10px] text-xene-muted uppercase tracking-widest text-center">
          Xene · Your artists, every platform · Milestone 1
        </p>
      </footer>
    </div>
  )
}
