// Individual feed card with IntersectionObserver from day one.
// Cards pause animations and lazy-load when off-screen.

import { useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import PlatformBadge from './PlatformBadge'
import SoundCloudPlayer from './SoundCloudPlayer'

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toUpperCase()
}

function formatCount(n) {
  if (!n) return null
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

export default function ArtistCard({ item, variant = 'square', index = 0 }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  const navigate = useNavigate()

  // IntersectionObserver: only animate/show content when card is in viewport
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { rootMargin: '80px', threshold: 0.05 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const isTrack = item.platform === 'soundcloud'
  const isRelease = item.content_type === 'release'

  const heightClass = {
    hero:    'min-h-[420px]',
    tall:    'min-h-[320px]',
    wide:    'min-h-[200px]',
    compact: 'min-h-[160px]',
    square:  'min-h-[240px]',
  }[variant]

  const artistSlug = item.artist_name.toLowerCase().replace(/\s+/g, '')

  return (
    <motion.article
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      animate={visible ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.45, delay: index * 0.06, ease: [0.25, 0.1, 0.25, 1] }}
      whileHover={visible ? { y: -3 } : {}}
      className={`
        relative group flex flex-col overflow-hidden cursor-pointer
        bg-xene-surface border border-xene-border
        transition-colors duration-300
        hover:border-xene-muted
        ${heightClass}
      `}
      onClick={() => navigate(`/artist/${artistSlug}`)}
    >
      {/* Artwork */}
      {item.artwork_url && (
        <div className="relative overflow-hidden flex-shrink-0"
          style={{ height: variant === 'compact' ? '80px' : variant === 'wide' ? '120px' : '180px' }}
        >
          {visible && (
            <img
              src={item.artwork_url}
              alt={item.title ?? item.artist_name}
              className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
              loading="lazy"
            />
          )}
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-xene-surface via-transparent to-transparent" />

          {/* Platform badge — top left */}
          <div className="absolute top-2 left-2">
            <PlatformBadge platform={item.platform} />
          </div>

          {/* Content type tag — top right */}
          {isRelease && (
            <div className="absolute top-2 right-2">
              <span className="font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 bg-xene-gold/20 text-xene-gold border border-xene-gold/30">
                Release
              </span>
            </div>
          )}
        </div>
      )}

      {/* Content body */}
      <div className="flex flex-col flex-1 p-3 gap-2">
        {/* Artist + date row */}
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] text-xene-gold uppercase tracking-widest truncate">
            {item.artist_name}
          </span>
          <span className="font-mono text-[9px] text-xene-muted flex-shrink-0">
            {formatDate(item.published_at)}
          </span>
        </div>

        {/* Title */}
        {item.title && (
          <h3 className={`font-display text-xene-text leading-none ${
            variant === 'hero' ? 'text-3xl' :
            variant === 'tall' ? 'text-2xl' :
            variant === 'wide' ? 'text-xl' :
            'text-lg'
          }`}>
            {item.title}
          </h3>
        )}

        {/* Body text */}
        {item.body && variant !== 'compact' && (
          <p className="font-body text-xene-text-dim text-xs leading-relaxed line-clamp-3">
            {item.body}
          </p>
        )}

        {/* SoundCloud player — only for track cards, only when visible */}
        {isTrack && visible && (
          <div className="mt-auto pt-2">
            <SoundCloudPlayer item={item} compact={variant === 'compact'} />
          </div>
        )}

        {/* Stats for non-track cards */}
        {!isTrack && (item.play_count || item.like_count) && (
          <div className="mt-auto pt-1 flex gap-3 font-mono text-[10px] text-xene-muted">
            {item.like_count && <span>{formatCount(item.like_count)} likes</span>}
          </div>
        )}

        {/* Bottom platform stripe — visual accent */}
        <div
          className="absolute bottom-0 left-0 right-0 h-px opacity-30"
          style={{
            backgroundColor: {
              soundcloud: '#ff5500',
              instagram: '#e1306c',
              bandcamp: '#4e9a06',
              beatport: '#5b7cfa',
              tiktok: '#ffffff',
            }[item.platform] ?? '#444',
          }}
        />
      </div>
    </motion.article>
  )
}
