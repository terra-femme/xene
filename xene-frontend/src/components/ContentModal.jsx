import { useEffect, useMemo, useState } from 'react'
import PlatformBadge from './PlatformBadge'
import SoundCloudPlayer from './SoundCloudPlayer'
import { scoutSocial } from '../lib/api'

const logger = {
  info: (...args) => console.log('[ContentModal]', ...args),
  warn: (...args) => console.warn('[ContentModal]', ...args),
}

const PLATFORM_NAMES = {
  soundcloud: { name: 'SoundCloud', color: '#ff5500' },
  instagram:  { name: 'Instagram',  color: '#e1306c' },
  bandcamp:   { name: 'Bandcamp',   color: '#4e9a06' },
  beatport:   { name: 'Beatport',   color: '#5b7cfa' },
  youtube:    { name: 'YouTube',    color: '#ff4444' },
  press:      { name: 'Press',      color: '#09b0ff' },
  twitch:     { name: 'Twitch',     color: '#9146ff' },
  tiktok:     { name: 'TikTok',     color: '#ffffff' },
}

export default function ContentModal({ item, onClose }) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [embedUrl, setEmbedUrl] = useState(null)
  const [embedLoading, setEmbedLoading] = useState(false)
  const [embedError, setEmbedError] = useState(null)

  useEffect(() => {
    if (!item) return
    logger.info('opened', item.id, item.platform)
    const handler = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [item, onClose])

  if (!item) return null

  const parsed = useMemo(() => {
    const url = item.external_url || ''
    const platform = item.platform
    const out = { platform, url, shortcode: null, videoId: null, username: null, trackId: null }

    if (platform === 'instagram') {
      // https://www.instagram.com/p/SHORTCODE/
      const m = url.match(/instagram\.com\/p\/([A-Za-z0-9_-]+)/i)
      if (m) out.shortcode = m[1]
      const u = url.match(/instagram\.com\/([A-Za-z0-9_.]+)/i)
      if (u && u[1] && u[1] !== 'p') out.username = u[1]
    }

    if (platform === 'youtube') {
      // https://www.youtube.com/watch?v=VIDEOID or https://youtu.be/VIDEOID
      const v = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([A-Za-z0-9_-]+)/i)
      if (v) out.videoId = v[1]
    }

    if (platform === 'soundcloud') {
      // Extract track ID from SoundCloud URL: https://soundcloud.com/user/track-name or https://api.soundcloud.com/tracks/ID
      const trackIdMatch = url.match(/soundcloud\.com\/.*\/(\d+)/)
      if (trackIdMatch) out.trackId = trackIdMatch[1]
    }

    return out
  }, [item.external_url, item.platform])

  useEffect(() => {
    setEmbedUrl(null)
    setEmbedError(null)
    setEmbedLoading(false)
    setPreviewOpen(false)

    if (!item?.external_url) return

    if (item.platform === 'instagram' && parsed.shortcode) {
      setEmbedUrl(`https://www.instagram.com/p/${parsed.shortcode}/embed`)
      return
    }

    if (item.platform === 'tiktok' && parsed.videoId) {
      setEmbedUrl(`https://www.tiktok.com/embed/v2/${parsed.videoId}`)
      return
    }

    if (item.platform === 'youtube' && parsed.videoId) {
      setEmbedUrl(`https://www.youtube.com/embed/${parsed.videoId}?autoplay=1`)
      return
    }

    if (item.platform === 'soundcloud') {
      setEmbedUrl(item.external_url)
      return
    }
  }, [item?.id, item?.external_url, item?.platform, parsed.shortcode, parsed.videoId])

  async function openPreview() {
    if (previewOpen) {
      setPreviewOpen(false)
      return
    }
    setPreviewOpen(true)

    if (embedUrl) return

    // TikTok notifications can still arrive as profile URLs (no /video/<id>).
    // Try backend scout; if unavailable/failing, open the canonical URL directly.
    if (item.platform === 'tiktok' && parsed.username) {
      setEmbedLoading(true)
      setEmbedError(null)
      try {
        const res = await scoutSocial({
          platform: 'tiktok',
          artistName: item.artist_name,
          username: parsed.username,
        })
        const url = res?.url || ''
        const m = url.match(/tiktok\.com\/@[^/]+\/video\/(\d+)/i)
        if (!m) throw new Error('Could not resolve a TikTok video URL')
        setEmbedUrl(`https://www.tiktok.com/embed/v2/${m[1]}`)
      } catch (e) {
        const fallback = item.external_url
        if (fallback) {
          window.open(fallback, '_blank', 'noopener,noreferrer')
          setEmbedError('Embed unavailable; opened TikTok in a new tab.')
        } else {
          setEmbedError(e?.message || 'Preview unavailable')
        }
      } finally {
        setEmbedLoading(false)
      }
      return
    }

    if (item.platform === 'tiktok' && item.external_url) {
      window.open(item.external_url, '_blank', 'noopener,noreferrer')
      setEmbedError('Embed unavailable; opened TikTok in a new tab.')
    }
  }

  const platMeta = PLATFORM_NAMES[item.platform] ?? { name: item.platform, color: '#c9a96e' }
  const isBandcamp = item.platform === 'bandcamp'
  const isArticle = item.platform === 'press'
  const paragraphs = item.body ? item.body.split('\n\n').filter(Boolean) : []
  const borderColor = isBandcamp ? 'rgba(78,154,6,0.25)' : 'rgba(255,255,255,0.08)'
  const headerBorder = isBandcamp ? 'rgba(78,154,6,0.12)' : 'rgba(255,255,255,0.06)'
  const canPreview = item.platform === 'instagram' || item.platform === 'tiktok' || item.platform === 'youtube' || item.platform === 'soundcloud'


  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6"
      style={{ background: 'rgba(0,0,0,0.88)', backdropFilter: 'blur(10px)' }}
    >
      <div
        className="w-full overflow-auto rounded"
        style={{
          maxWidth: 660,
          maxHeight: '90vh',
          background: '#0f0f0f',
          border: `1px solid ${borderColor}`,
          boxShadow: isBandcamp
            ? '0 40px 80px rgba(0,0,0,0.9), 0 0 60px rgba(78,154,6,0.07)'
            : '0 40px 80px rgba(0,0,0,0.8)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-start justify-between gap-4 px-5 sm:px-6 py-4"
          style={{ borderBottom: `1px solid ${headerBorder}` }}
        >
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <PlatformBadge platform={item.platform} size="lg" />
              <span
                className="font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 border"
                style={{ color: '#c9a96e', borderColor: '#c9a96e44', background: '#c9a96e18' }}
              >
                {item.content_type}
              </span>
            </div>
            <h3 className="font-display text-xl sm:text-2xl text-xene-text leading-none mt-1">
              {item.title}
            </h3>
            <span
              className="font-mono text-[11px] tracking-wider"
              style={{ color: isBandcamp ? '#4e9a06' : '#c9a96e' }}
            >
              {item.artist_name}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-xene-muted text-lg leading-none flex-shrink-0 mt-0.5 hover:text-xene-text transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-5 sm:px-6 py-5 flex flex-col gap-5">
          {/* Instagram/TikTok embeds — official embed endpoints */}
          {canPreview && item.external_url && (
            <div className="flex flex-col gap-3">
              <button
                onClick={openPreview}
                className="self-start inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-wider uppercase border rounded px-4 py-2.5 no-underline transition-colors"
                style={{
                  color: platMeta.color,
                  borderColor: platMeta.color + '44',
                  background: platMeta.color + '18',
                }}
              >
                {previewOpen ? 'Hide preview' : 'Preview'}
              </button>

              {previewOpen && (
                <div
                  className="w-full overflow-hidden rounded"
                  style={{ border: '1px solid rgba(255,255,255,0.08)', background: '#070707' }}
                >
                  {embedLoading && (
                    <div className="p-6">
                      <span className="font-mono text-[10px] text-xene-muted uppercase tracking-widest">
                        Loading preview…
                      </span>
                    </div>
                  )}

                  {!embedLoading && embedError && (
                    <div className="p-6 flex flex-col gap-3">
                      <span className="font-mono text-[10px] text-xene-muted uppercase tracking-widest">
                        {embedError}
                      </span>
                      <a
                        href={item.external_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="self-start font-mono text-xs uppercase tracking-widest border rounded px-4 py-2.5 no-underline"
                        style={{
                          color: platMeta.color,
                          borderColor: platMeta.color + '55',
                          background: platMeta.color + '18',
                        }}
                      >
                        Open on {platMeta.name} →
                      </a>
                    </div>
                  )}

                  {!embedLoading && !embedError && embedUrl && item.platform === 'soundcloud' && (
                    <SoundCloudPlayer
                      item={item}
                      trackUrl={embedUrl}
                      artistName={item.artist_name}
                      trackTitle={item.title}
                    />
                  )}

                  {!embedLoading && !embedError && embedUrl && item.platform !== 'soundcloud' && (
                    <iframe
                      src={embedUrl}
                      className="w-full border-0"
                      style={{ minHeight: item.platform === 'tiktok' ? 600 : 450 }}
                      sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
                      title={`${platMeta.name} preview`}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Press/Article — open link button */}
          {isArticle && item.external_url && (
            <a
              href={item.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="self-start inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-wider uppercase border rounded px-4 py-2.5 no-underline transition-colors"
              style={{
                color: platMeta.color,
                borderColor: platMeta.color + '44',
                background: platMeta.color + '18',
              }}
            >
              Read on source →
            </a>
          )}

          {/* Artwork visual */}
          {item.artwork_url && (
            <img
              src={item.artwork_url}
              alt={item.title}
              className="w-full rounded object-cover"
              style={{ maxHeight: 360 }}
            />
          )}

          {/* Bandcamp editorial quote treatment */}
          {isBandcamp && paragraphs.length > 0 && (
            <div>
              <div
                className="font-display select-none"
                style={{ fontSize: 80, lineHeight: 0.65, color: 'rgba(78,154,6,0.10)', marginBottom: 8 }}
              >
                &ldquo;
              </div>
              <div style={{ borderLeft: '2px solid rgba(78,154,6,0.28)', paddingLeft: 22 }}>
                {paragraphs.map((p, i) => (
                  <p
                    key={i}
                    className="font-body italic"
                    style={{
                      fontSize: i === 0 ? 15 : 13,
                      fontWeight: i === 0 ? 500 : 400,
                      color: i === 0 ? '#b0b0b0' : '#6a6a6a',
                      lineHeight: 1.8,
                      marginBottom: i < paragraphs.length - 1 ? 18 : 0,
                    }}
                  >
                    {p}
                  </p>
                ))}
              </div>
              <div
                className="font-display select-none text-right"
                style={{ fontSize: 80, lineHeight: 0.65, color: 'rgba(78,154,6,0.07)', marginTop: 8 }}
              >
                &rdquo;
              </div>
            </div>
          )}

          {/* Plain body text for non-Bandcamp */}
          {!isBandcamp && item.body && (
            <p className="font-body text-xs text-xene-muted leading-relaxed">{item.body}</p>
          )}

          {/* External link */}
          {item.external_url && (
            <a
              href={item.external_url}
              target="_blank"
              rel="noopener noreferrer"
              className="self-start inline-flex items-center gap-2 font-mono text-xs font-bold tracking-wider uppercase border rounded px-4 py-2.5 no-underline transition-colors"
              style={{
                color: platMeta.color,
                borderColor: platMeta.color + '44',
                background: platMeta.color + '18',
              }}
              onMouseEnter={e => e.currentTarget.style.background = platMeta.color + '30'}
              onMouseLeave={e => e.currentTarget.style.background = platMeta.color + '18'}
            >
              Open on {platMeta.name} →
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
