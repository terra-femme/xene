import { useState } from 'react'
import PlatformBadge from './PlatformBadge'
import { usePlayer } from '../context/PlayerContext'

const logger = {
  info: (...args) => console.log('[MobileCard]', ...args),
  warn: (...args) => console.warn('[MobileCard]', ...args),
}

const CONTENT_TYPE_META = {
  track:   { label: 'TRACK',   color: '#ff5500' },
  mix:     { label: 'MIX',     color: '#c9a96e' },
  release: { label: 'RELEASE', color: '#4e9a06' },
  post:    { label: 'POST',    color: '#e1306c' },
  image:   { label: 'PHOTO',   color: '#e1306c' },
  video:   { label: 'VIDEO',   color: '#ff4444' },
  article: { label: 'PRESS',   color: '#09b0ff' },
}

function TypePill({ type }) {
  const meta = CONTENT_TYPE_META[type] ?? { label: type.toUpperCase(), color: '#888' }
  return (
    <span
      className="font-mono text-[8px] font-bold tracking-widest rounded px-1.5 py-0.5 whitespace-nowrap"
      style={{
        color: meta.color,
        background: meta.color + '18',
        border: `1px solid ${meta.color}33`,
      }}
    >
      {meta.label}
    </span>
  )
}

export default function MobileCard({ item, onClick, isLast, size = 'default' }) {
  const [hov, setHov] = useState(false)
  const player = usePlayer()
  const isBandcamp = item.platform === 'bandcamp'
  const isArticle = item.content_type === 'article'
  const paragraphs = item.body ? item.body.split('\n\n').filter(Boolean) : []
  const isPlayable = ['soundcloud', 'youtube'].includes(item.platform)

  const isSmall = size === 'small'

  // Simple touch detection
  const isTouch = typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0)
  const showPlayButton = isPlayable && (hov || isTouch)

  const logger_prefix = `[MobileCard] ${item.title}`

  const handlePlayClick = (e) => {
    e.stopPropagation()
    e.preventDefault()
    logger.info(logger_prefix, 'play clicked')
    player.playTrack(item)
  }

  // Sizing tokens — small variant fits the 227px right column
  const thumbSize  = isSmall ? 39 : 60
  const cardMargin = isSmall ? '0 6px' : '0 14px'
  const cardPad    = isSmall ? '7px 8px' : '12px 14px'
  const cardGap    = isSmall ? 7 : 10
  const cardMb     = isLast ? (isSmall ? 6 : 10) : 2

  return (
    <div
      onClick={() => {
        logger.info(logger_prefix, 'Card clicked | isPlayable:', isPlayable)
        if (isPlayable) {
          // Playable items (SC/YT) open modal with embedded player
          onClick?.(item)
        } else if (item.external_url) {
          // Non-playable items open source link directly
          window.open(item.external_url, '_blank', 'noopener,noreferrer')
        }
      }}
      onMouseEnter={() => { setHov(true) }}
      onMouseLeave={() => { setHov(false) }}
      className="transition-colors duration-75 cursor-pointer border rounded-lg active:scale-[0.98]"
      style={{
        margin: cardMargin,
        marginBottom: cardMb,
        padding: cardPad,
        borderRadius: 8,
        background: isSmall ? (hov ? '#f5f5f5' : '#ffffff') : (hov ? '#161616' : '#111'),
        borderColor: isSmall ? '#e0e0e0' : 'rgba(255,255,255,0.05)',
        display: 'flex',
        gap: cardGap,
      }}
    >
      {/* Artwork thumbnail — left */}
      {item.artwork_url && (
        <div
          style={{
            position: 'relative',
            width: thumbSize,
            height: thumbSize,
            borderRadius: 5,
            flexShrink: 0,
            overflow: 'hidden',
            backgroundColor: '#1a1a1a',
          }}
        >
          <img
            src={item.artwork_url}
            alt={item.title}
            loading="lazy"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
          {showPlayButton && (
            <button
              onClick={handlePlayClick}
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: isTouch ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.4)',
                border: 'none',
                cursor: 'pointer',
                transition: 'background 0.2s',
                pointerEvents: 'auto',
              }}
            >
              <div
                style={{
                  width: isSmall ? 20 : 30,
                  height: isSmall ? 20 : 30,
                  borderRadius: '50%',
                  background: 'rgba(255, 85, 0, 0.9)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
                }}
              >
                <svg
                  width={isSmall ? 10 : 16}
                  height={isSmall ? 10 : 16}
                  viewBox="0 0 24 24"
                  fill="white"
                >
                  <path d="M8 5v14l11-7z" />
                </svg>
              </div>
            </button>
          )}
        </div>
      )}

      {/* Content — right */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Type pill + Platform badge row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <TypePill type={item.content_type} />
          <PlatformBadge platform={item.platform} />
        </div>

        {/* Title — clickable link to external source */}
        <div style={{ position: 'relative', zIndex: 10 }}>
          <a
            href={item.external_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              logger.info(logger_prefix, 'Title clicked | isPlayable:', isPlayable)
              if (isPlayable) {
                // Playable items open modal
                onClick?.(item)
              } else if (item.external_url) {
                // Non-playable items open link directly
                window.open(item.external_url, '_blank', 'noopener,noreferrer')
              }
            }}
            className={`block font-display font-semibold leading-snug truncate transition-colors cursor-pointer hover:underline ${isSmall ? 'text-xs' : 'text-sm'}`}
            style={{
              color: isSmall ? '#000000' : ((hov || isTouch) ? '#e8e8e8' : '#ccc'),
              marginBottom: isSmall ? 2 : 4,
              textDecoration: 'none',
              pointerEvents: 'auto',
            }}
          >
            {item.title}
          </a>
        </div>

        {/* Body snippet */}
        {isBandcamp && isArticle && paragraphs.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 4 }}>
            {paragraphs.map((p, idx) => (
              <div
                key={idx}
                className="font-body italic"
                style={{
                  fontSize: 9,
                  color: '#666',
                  lineHeight: 1.4,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                "{p}"
              </div>
            ))}
          </div>
        )}
        {(!isBandcamp || !isArticle) && paragraphs.length > 0 && (
          <div
            className="font-body text-[10px] leading-tight"
            style={{
              color: isSmall ? '#888888' : '#555',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {item.body}
          </div>
        )}
      </div>
    </div>
  )
}
