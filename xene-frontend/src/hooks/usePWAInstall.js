import { useState, useEffect } from 'react'

// Capture the browser's install prompt before it fires automatically.
// We'll hold it and trigger at the right moment (after first platform connect).
let deferredPrompt = null

export function usePWAInstall() {
  const [canInstall, setCanInstall] = useState(false)
  const [isInstalled, setIsInstalled] = useState(
    window.matchMedia('(display-mode: standalone)').matches
  )

  // iOS detection — Safari doesn't fire beforeinstallprompt
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
  const isIOSInstallable = isIOS && !isInstalled

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault()
      deferredPrompt = e
      setCanInstall(true)
    }

    window.addEventListener('beforeinstallprompt', handler)

    // Track if user installs via the prompt
    window.addEventListener('appinstalled', () => {
      setIsInstalled(true)
      setCanInstall(false)
      deferredPrompt = null
    })

    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
    }
  }, [])

  const triggerInstall = async () => {
    if (!deferredPrompt) return false
    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    deferredPrompt = null
    setCanInstall(false)
    return outcome === 'accepted'
  }

  return { canInstall, isInstalled, isIOSInstallable, triggerInstall }
}
