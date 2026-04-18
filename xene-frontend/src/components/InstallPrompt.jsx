// PWA install prompt modal.
// Android: fires native browser prompt.
// iOS: shows custom bottom sheet with "Add to Home Screen" instructions.

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { usePWAInstall } from '../hooks/usePWAInstall'

export default function InstallPrompt() {
  const { canInstall, isInstalled, isIOSInstallable, triggerInstall } = usePWAInstall()
  const [dismissed, setDismissed] = useState(false)
  const [showIOSSheet, setShowIOSSheet] = useState(false)

  // Don't show if already installed or dismissed
  if (isInstalled || dismissed) return null
  if (!canInstall && !isIOSInstallable) return null

  const handleInstall = async () => {
    if (isIOSInstallable) {
      setShowIOSSheet(true)
      return
    }
    await triggerInstall()
    setDismissed(true)
  }

  return (
    <>
      {/* Banner prompt */}
      <AnimatePresence>
        {!showIOSSheet && (
          <motion.div
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed bottom-0 left-0 right-0 z-50 p-4 safe-area-bottom"
          >
            <div className="max-w-lg mx-auto bg-xene-surface border border-xene-gold/30 p-4 flex items-center gap-4">
              <div className="flex-1">
                <p className="font-display text-xl text-xene-text leading-none">Add Xene</p>
                <p className="font-mono text-[11px] text-xene-text-dim mt-1">
                  Your artists. Every platform. One feed.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setDismissed(true)}
                  className="font-mono text-[11px] text-xene-muted hover:text-xene-text-dim px-3 py-2 border border-xene-border uppercase tracking-wider transition-colors"
                >
                  Later
                </button>
                <button
                  onClick={handleInstall}
                  className="font-mono text-[11px] text-xene-bg bg-xene-gold hover:bg-xene-gold/80 px-4 py-2 uppercase tracking-wider transition-colors"
                >
                  Install
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* iOS bottom sheet */}
      <AnimatePresence>
        {showIOSSheet && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 z-50"
              onClick={() => setShowIOSSheet(false)}
            />
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', stiffness: 300, damping: 32 }}
              className="fixed bottom-0 left-0 right-0 z-50 bg-xene-surface border-t border-xene-gold/30 p-6 pb-10"
            >
              <div className="w-8 h-px bg-xene-muted mx-auto mb-6" />
              <p className="font-display text-2xl text-xene-text mb-4">Add to Home Screen</p>
              <ol className="space-y-3 font-body text-sm text-xene-text-dim">
                <li className="flex items-start gap-3">
                  <span className="font-mono text-xene-gold text-xs mt-0.5">01</span>
                  <span>Tap the <strong className="text-xene-text">Share</strong> button at the bottom of Safari (the box with an arrow pointing up)</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="font-mono text-xene-gold text-xs mt-0.5">02</span>
                  <span>Scroll down and tap <strong className="text-xene-text">Add to Home Screen</strong></span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="font-mono text-xene-gold text-xs mt-0.5">03</span>
                  <span>Tap <strong className="text-xene-text">Add</strong> in the top right corner</span>
                </li>
              </ol>
              <button
                onClick={() => { setShowIOSSheet(false); setDismissed(true) }}
                className="mt-6 w-full font-mono text-xs uppercase tracking-widest py-3 border border-xene-border text-xene-text-dim hover:border-xene-muted transition-colors"
              >
                Done
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
