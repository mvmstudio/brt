"use client"

import { useRef, useState, useCallback, useEffect, type ReactNode } from "react"
import { ArrowDown, Loader2 } from "lucide-react"

interface PullToRefreshProps {
  onRefresh: () => Promise<void>
  children: ReactNode
  className?: string
}

const THRESHOLD = 64
const MAX_PULL = 120
const RESISTANCE = 0.4

export default function PullToRefresh({ onRefresh, children, className }: PullToRefreshProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const startY = useRef(0)
  const startX = useRef(0)
  const pulling = useRef(false)
  const directionLocked = useRef<"vertical" | "horizontal" | null>(null)

  const [pullDistance, setPullDistance] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (refreshing) return
    const el = containerRef.current
    if (!el || el.scrollTop > 0) return

    startY.current = e.touches[0].clientY
    startX.current = e.touches[0].clientX
    pulling.current = true
    directionLocked.current = null
  }, [refreshing])

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!pulling.current || refreshing) return

    const deltaY = e.touches[0].clientY - startY.current
    const deltaX = e.touches[0].clientX - startX.current

    // Direction lock: decide on first significant move
    if (!directionLocked.current) {
      const absDx = Math.abs(deltaX)
      const absDy = Math.abs(deltaY)
      if (absDx > 8 || absDy > 8) {
        directionLocked.current = absDy >= absDx ? "vertical" : "horizontal"
      }
      if (directionLocked.current !== "vertical") return
    }

    if (directionLocked.current !== "vertical") return

    if (deltaY > 0) {
      e.preventDefault()
      const distance = Math.min(deltaY * RESISTANCE, MAX_PULL)
      setPullDistance(distance)
    } else {
      setPullDistance(0)
    }
  }, [refreshing])

  const handleTouchEnd = useCallback(async () => {
    if (!pulling.current || refreshing) return
    pulling.current = false
    directionLocked.current = null

    if (pullDistance >= THRESHOLD) {
      setRefreshing(true)
      setPullDistance(THRESHOLD)
      try {
        await onRefresh()
      } finally {
        setRefreshing(false)
        setPullDistance(0)
      }
    } else {
      setPullDistance(0)
    }
  }, [pullDistance, refreshing, onRefresh])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    el.addEventListener("touchstart", handleTouchStart, { passive: true })
    el.addEventListener("touchmove", handleTouchMove, { passive: false })
    el.addEventListener("touchend", handleTouchEnd, { passive: true })

    return () => {
      el.removeEventListener("touchstart", handleTouchStart)
      el.removeEventListener("touchmove", handleTouchMove)
      el.removeEventListener("touchend", handleTouchEnd)
    }
  }, [handleTouchStart, handleTouchMove, handleTouchEnd])

  const progress = Math.min(pullDistance / THRESHOLD, 1)
  const rotation = progress * 180

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ overscrollBehaviorY: "contain" }}
    >
      <div
        className="ptr-indicator"
        style={{
          height: pullDistance > 0 || refreshing ? `${pullDistance}px` : "0px",
          transition: pulling.current ? "none" : "height 0.3s ease",
        }}
      >
        {(pullDistance > 0 || refreshing) && (
          <div className="ptr-icon">
            {refreshing ? (
              <Loader2 size={22} strokeWidth={1.25} className="ptr-spinner" />
            ) : (
              <ArrowDown
                size={22}
                strokeWidth={1.25}
                style={{
                  transform: `rotate(${rotation}deg)`,
                  transition: "transform 0.1s ease",
                  opacity: 0.3 + progress * 0.7,
                }}
              />
            )}
          </div>
        )}
      </div>
      {children}
    </div>
  )
}
