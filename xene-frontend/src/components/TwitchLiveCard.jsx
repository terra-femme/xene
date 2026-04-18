import { motion } from 'framer-motion'

function formatViewers(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export default function TwitchLiveCard({ stream, index = 0 }) {
  return (
    <motion.a
      href={stream.stream_url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: [0.25, 0.1, 0.25, 1] }}
      className="
        relative flex gap-3 overflow-hidden cursor-pointer group
        bg-xene-surface border border-[#9146ff]/40
        hover:border-[#9146ff]/80 transition-colors duration-300
        p-3
      "
    >
      {/* Thumbnail */}
      {stream.thumbnail_url && (
        <div className="relative flex-shrink-0 w-24 h-16 overflow-hidden">
          <img
            src={stream.thumbnail_url}
            alt={stream.stream_title}
            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
            loading="lazy"
          />
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent to-xene-surface/40" />
        </div>
      )}

      {/* Info */}
      <div className="flex flex-col justify-center gap-1 min-w-0">
        {/* LIVE badge + artist name */}
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 bg-[#9146ff]/20 border border-[#9146ff]/50 text-[#bf94ff]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#9146ff] animate-pulse" />
            Live
          </span>
          <span className="font-mono text-[10px] text-xene-gold uppercase tracking-widest truncate">
            {stream.twitch_login}
          </span>
        </div>

        {/* Stream title */}
        <p className="font-display text-xene-text text-sm leading-tight truncate">
          {stream.stream_title || 'Live on Twitch'}
        </p>

        {/* Game + viewer count */}
        <div className="flex items-center gap-3 font-mono text-[10px] text-xene-muted">
          {stream.game_name && <span>{stream.game_name}</span>}
          {stream.viewer_count > 0 && (
            <span>{formatViewers(stream.viewer_count)} watching</span>
          )}
        </div>
      </div>

      {/* Twitch purple accent stripe */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-[#9146ff] opacity-40" />
    </motion.a>
  )
}
