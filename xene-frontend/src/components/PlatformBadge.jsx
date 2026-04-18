// Platform badge — color-coded tag per source platform

const PLATFORM_META = {
  soundcloud: { label: 'SC', color: '#ff5500', bg: 'rgba(255,85,0,0.12)' },
  instagram:  { label: 'IG', color: '#e1306c', bg: 'rgba(225,48,108,0.12)' },
  bandcamp:   { label: 'BC', color: '#4e9a06', bg: 'rgba(78,154,6,0.12)' },
  beatport:   { label: 'BP', color: '#5b7cfa', bg: 'rgba(91,124,250,0.12)' },
  tiktok:     { label: 'TT', color: '#ffffff', bg: 'rgba(255,255,255,0.08)' },
}

export default function PlatformBadge({ platform, size = 'sm' }) {
  const meta = PLATFORM_META[platform] ?? { label: platform.toUpperCase(), color: '#888', bg: 'rgba(136,136,136,0.1)' }

  const sizeClass = size === 'lg'
    ? 'text-xs px-2 py-1 tracking-widest'
    : 'text-[10px] px-1.5 py-0.5 tracking-widest'

  return (
    <span
      className={`font-mono font-medium uppercase border ${sizeClass}`}
      style={{
        color: meta.color,
        backgroundColor: meta.bg,
        borderColor: meta.color + '40',
        letterSpacing: '0.15em',
      }}
    >
      {meta.label}
    </span>
  )
}
