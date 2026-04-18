import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchOembed } from '../lib/api'

const BARS = Array.from({ length: 48 }, (_, i) => ({
  id: i,
  delay: (i % 7) * 0.07,
  heightRatio: 0.2 + Math.abs(Math.sin(i * 0.4 + 1.2)) * 0.8,
}))

function formatCount(n) {
  if (!n) return null
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export default function SoundCloudPlayer({ item, compact = false }) {
  const [playerOpen, setPlayerOpen] = useState(false)

  // Fetch oEmbed iframe HTML when the user clicks play — lazy, not on mount
  const { data: oembed, isFetching: loadingOembed } = useQuery({
    queryKey: ['oembed', item.external_url],
    queryFn: () => fetchOembed(item.external_url),
    enabled: playerOpen,           // only fires after play click
    staleTime: Infinity,           // oEmbed for a track never changes
    retry: false,
  })

  return (
    <div className="flex flex-col gap-2">
      {/* Waveform + play button row */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setPlayerOpen(p => !p)}
          className="relative flex-shrink-0 w-8 h-8 rounded-full border border-xene-sc/40 bg-xene-sc/10 flex items-center justify-center transition-all hover:bg-xene-sc/20 hover:border-xene-sc/70"
          aria-label={playerOpen ? 'Close player' : 'Play on SoundCloud'}
        >
          <AnimatePresence mode="wait" initial={false}>
            {loadingOembed ? (
              <motion.span
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="w-3 h-3 border border-xene-sc border-t-transparent rounded-full animate-spin"
              />
            ) : playerOpen ? (
              <motion.span
                key="pause"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }}
                transition={{ duration: 0.12 }}
                className="flex gap-0.5"
              >
                <span className="w-[3px] h-3 bg-xene-sc block" />
                <span className="w-[3px] h-3 bg-xene-sc block" />
              </motion.span>
            ) : (
              <motion.span
                key="play"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }}
                transition={{ duration: 0.12 }}
                style={{
                  width: 0,
                  height: 0,
                  borderTop: '5px solid transparent',
                  borderBottom: '5px solid transparent',
                  borderLeft: '8px solid #ff5500',
                  marginLeft: '2px',
                }}
              />
            )}
          </AnimatePresence>
        </button>

        {/* Animated waveform bars */}
        <div className="flex items-end gap-px flex-1 h-8 overflow-hidden">
          {BARS.map(bar => (
            <div
              key={bar.id}
              className="flex-1 bg-xene-sc/30 origin-bottom"
              style={{
                height: `${bar.heightRatio * 100}%`,
                ...(playerOpen ? {
                  animation: `waveform ${0.8 + bar.delay}s ease-in-out ${bar.delay}s infinite alternate`,
                  backgroundColor: `rgba(255,85,0,${0.4 + bar.heightRatio * 0.4})`,
                } : {
                  transform: `scaleY(${bar.heightRatio * 0.6 + 0.1})`,
                  backgroundColor: 'rgba(255,85,0,0.2)',
                }),
              }}
            />
          ))}
        </div>
      </div>

      {/* oEmbed player — appears below waveform when play is clicked */}
      <AnimatePresence>
        {playerOpen && (
          <motion.div
            key="player"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            {oembed?.html ? (
              <div
                className="rounded overflow-hidden"
                dangerouslySetInnerHTML={{ __html: oembed.html }}
              />
            ) : !loadingOembed && (
              // Fallback: direct link if oEmbed not available (no backend / blocked)
              <a
                href={item.external_url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[10px] text-xene-sc underline"
              >
                Open on SoundCloud →
              </a>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Metadata row */}
      {!compact && (
        <div className="flex items-center gap-3 font-mono text-[10px] text-xene-text-dim">
          {item.play_count && <span>{formatCount(item.play_count)} plays</span>}
          {item.like_count && <span>{formatCount(item.like_count)} likes</span>}
        </div>
      )}
    </div>
  )
}
