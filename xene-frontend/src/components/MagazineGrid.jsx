// Main animated magazine feed layout.
// Asymmetric CSS Grid — intentionally breaks uniform card patterns.
// Cards vary in size based on content type and position.

import { useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ArtistCard from './ArtistCard'

// Assign visual weight to each card based on its position in the sorted feed.
// Pattern repeats every 7 cards to keep the grid feeling magazine-like.
const LAYOUT_PATTERN = [
  { variant: 'hero',    gridClass: 'col-span-2 row-span-2' },
  { variant: 'tall',    gridClass: 'col-span-1 row-span-2' },
  { variant: 'square',  gridClass: 'col-span-1' },
  { variant: 'square',  gridClass: 'col-span-1' },
  { variant: 'compact', gridClass: 'col-span-1' },
  { variant: 'wide',    gridClass: 'col-span-2' },
  { variant: 'compact', gridClass: 'col-span-1' },
]

export default function MagazineGrid({ items, loading }) {
  // Sort: newest first
  const sorted = useMemo(() => {
    if (!items) return []
    return [...items].sort((a, b) => new Date(b.published_at) - new Date(a.published_at))
  }, [items])

  if (loading) {
    return <MagazineGridSkeleton />
  }

  if (!sorted.length) {
    return (
      <div className="flex items-center justify-center py-32">
        <p className="font-mono text-xene-muted text-sm tracking-widest uppercase">No items</p>
      </div>
    )
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={sorted.map(i => i.id).join('-')}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
        className="grid grid-cols-3 gap-px bg-xene-border"
        style={{ gridAutoRows: 'auto' }}
      >
        {sorted.map((item, i) => {
          const layout = LAYOUT_PATTERN[i % LAYOUT_PATTERN.length]
          return (
            <div key={item.id} className={`bg-xene-bg ${layout.gridClass}`}>
              <ArtistCard
                item={item}
                variant={layout.variant}
                index={i}
              />
            </div>
          )
        })}
      </motion.div>
    </AnimatePresence>
  )
}

// Skeleton loader — matches the grid shape
function MagazineGridSkeleton() {
  const skeletons = LAYOUT_PATTERN.concat(LAYOUT_PATTERN.slice(0, 3))
  return (
    <div className="grid grid-cols-3 gap-px bg-xene-border">
      {skeletons.map((layout, i) => (
        <div key={i} className={`bg-xene-bg ${layout.gridClass}`}>
          <div
            className="relative overflow-hidden bg-xene-surface border border-xene-border"
            style={{ minHeight: layout.variant === 'hero' ? 420 : layout.variant === 'tall' ? 320 : 200 }}
          >
            {/* Shimmer scan line */}
            <div className="absolute inset-0 overflow-hidden">
              <div
                className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/[0.03] to-transparent"
                style={{ animation: 'scan 2s linear infinite', animationDelay: `${i * 0.15}s` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
