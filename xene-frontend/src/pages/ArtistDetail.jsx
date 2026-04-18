// Single artist all-platform view.
// Shows every piece of content from a specific artist grouped by platform.

import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { fetchArtistDetail } from '../lib/api'
import ArtistCard from '../components/ArtistCard'
import PlatformBadge from '../components/PlatformBadge'

const PLATFORM_ORDER = ['soundcloud', 'bandcamp', 'beatport', 'instagram', 'tiktok']

export default function ArtistDetail() {
  const { artistId } = useParams()
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['artist', artistId],
    queryFn: () => fetchArtistDetail(artistId),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-xene-bg flex items-center justify-center">
        <p className="font-mono text-xene-muted text-xs uppercase tracking-widest animate-pulse-gold">Loading</p>
      </div>
    )
  }

  if (isError || !data?.artist) {
    return (
      <div className="min-h-screen bg-xene-bg flex flex-col items-center justify-center gap-4">
        <p className="font-mono text-xene-muted text-xs uppercase tracking-widest">Artist not found</p>
        <button onClick={() => navigate('/')} className="font-mono text-[11px] text-xene-gold border border-xene-gold/40 px-4 py-2 hover:bg-xene-gold/10 transition-colors uppercase tracking-widest">
          Back to Feed
        </button>
      </div>
    )
  }

  const { artist, feed } = data

  // Group feed items by platform, ordered
  const byPlatform = PLATFORM_ORDER.reduce((acc, p) => {
    const items = feed.filter(i => i.platform === p)
    if (items.length) acc[p] = items
    return acc
  }, {})

  return (
    <div className="min-h-screen bg-xene-bg">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-xene-bg/95 backdrop-blur-sm border-b border-xene-border">
        <div className="flex items-center gap-4 px-4 py-3">
          <button
            onClick={() => navigate(-1)}
            className="font-mono text-[11px] text-xene-muted hover:text-xene-text border border-xene-border hover:border-xene-muted px-3 py-1.5 uppercase tracking-widest transition-colors flex-shrink-0"
          >
            ← Back
          </button>
          <span className="font-display text-3xl text-xene-text tracking-widest truncate">
            {artist.name.toUpperCase()}
          </span>
        </div>
      </header>

      {/* Platform presence badges */}
      <div className="px-4 py-3 border-b border-xene-border flex items-center gap-2 flex-wrap">
        <span className="font-mono text-[10px] text-xene-muted uppercase tracking-widest mr-1">On:</span>
        {artist.platforms.map(p => (
          <PlatformBadge key={p} platform={p} size="lg" />
        ))}
      </div>

      {/* Content by platform */}
      <main className="divide-y divide-xene-border">
        {Object.entries(byPlatform).map(([platform, items]) => (
          <section key={platform} className="py-6">
            <div className="px-4 mb-4 flex items-center gap-3">
              <PlatformBadge platform={platform} size="lg" />
              <span className="font-mono text-[10px] text-xene-muted uppercase tracking-widest">
                {items.length} item{items.length !== 1 ? 's' : ''}
              </span>
            </div>

            {/* 3-column grid per platform */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-xene-border px-0">
              {items.map((item, i) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.07, duration: 0.35 }}
                  className="bg-xene-bg"
                >
                  <ArtistCard item={item} variant="square" index={i} />
                </motion.div>
              ))}
            </div>
          </section>
        ))}
      </main>

      <footer className="border-t border-xene-border px-4 py-6">
        <p className="font-mono text-[10px] text-xene-muted uppercase tracking-widest text-center">
          Xene · {artist.name}
        </p>
      </footer>
    </div>
  )
}
