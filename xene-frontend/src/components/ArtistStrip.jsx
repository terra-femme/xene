// Horizontal scrollable artist pill selector.
// "All" pill shows the full feed. Artist pills filter by artist.

import { motion } from 'framer-motion'

const PLATFORM_DOT_COLOR = {
  soundcloud: '#ff5500',
  instagram:  '#e1306c',
  bandcamp:   '#4e9a06',
  beatport:   '#5b7cfa',
  tiktok:     '#ffffff',
}

export default function ArtistStrip({ artists, selected, onSelect, liveLogins = new Map() }) {
  const pills = [{ id: null, name: 'All', platforms: [] }, ...artists]

  return (
    <div className="relative">
      {/* Fade edges to indicate scroll */}
      <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-xene-bg to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-xene-bg to-transparent z-10 pointer-events-none" />

      <div
        className="flex gap-2 overflow-x-auto px-4 pb-1 scrollbar-none"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {pills.map(pill => {
          const isActive = selected === pill.id
          return (
            <motion.button
              key={pill.id ?? 'all'}
              onClick={() => onSelect(pill.id)}
              whileTap={{ scale: 0.95 }}
              className={`
                relative flex-shrink-0 flex items-center gap-1.5
                px-4 py-1.5 border font-mono text-xs uppercase tracking-widest
                transition-colors duration-200
                ${isActive
                  ? 'border-xene-gold text-xene-gold bg-xene-gold/10'
                  : 'border-xene-border text-xene-text-dim bg-transparent hover:border-xene-muted hover:text-xene-text'}
              `}
            >
              {/* Twitch LIVE pulse dot */}
              {pill.twitch_login && liveLogins.has(pill.twitch_login) && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#9146ff] animate-pulse flex-shrink-0" title="Live on Twitch" />
              )}
              {/* Platform color dots */}
              {pill.platforms?.length > 0 && (
                <span className="flex gap-0.5">
                  {pill.platforms.map(p => (
                    <span
                      key={p}
                      className="w-1 h-1 rounded-full"
                      style={{ backgroundColor: PLATFORM_DOT_COLOR[p] ?? '#888' }}
                    />
                  ))}
                </span>
              )}
              {pill.name}
              {/* Active underline */}
              {isActive && (
                <motion.span
                  layoutId="strip-indicator"
                  className="absolute bottom-0 left-0 right-0 h-px bg-xene-gold"
                />
              )}
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
