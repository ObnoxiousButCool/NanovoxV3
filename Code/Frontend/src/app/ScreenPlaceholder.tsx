/**
 * A screen the design system can host but that nobody has built yet.
 *
 * Deliberately says so in plain words rather than rendering an empty panel
 * or a plausible-looking skeleton. An empty screen reads as "no data", which
 * is the one thing this application must never accidentally claim — the same
 * reason a withheld figure is never a zero.
 */

import { useLocation } from 'react-router-dom'

import { NAV_ITEMS } from '@/shared/design/navigation'
import { FilterBar } from '@/shared/filters/FilterBar'

export function ScreenPlaceholder({ phase }: { phase: string }) {
  const { pathname } = useLocation()
  const item = NAV_ITEMS.find((nav) => pathname.startsWith(nav.to))

  return (
    <section className="nv-placeholder">
      <h1>{item?.label ?? 'Screen'}</h1>
      <p className="nv-lede">{item?.hint}</p>
      <FilterBar />
      <p>
        Not built yet — this screen arrives in <b>{phase}</b>. The shell, the
        tokens and the theme around it are real; nothing inside it is, and no
        figure is shown rather than a placeholder one.
      </p>
    </section>
  )
}
