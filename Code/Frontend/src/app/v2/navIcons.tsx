import type { ReactNode } from 'react'

/**
 * The Overview rail's small inline SVGs.
 *
 * These follow the line style and silhouettes in Saloni's shared frame,
 * without adding an icon package just for this navigation.
 */

type NavIconName = 'overview' | 'accounts' | 'actions' | 'calls' | 'agents' | 'brokers' | 'emerging'

const ICONS: Record<NavIconName, ReactNode> = {
  overview: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="1.5" />
      <path d="M10 4v16M10 10h11" />
    </>
  ),
  accounts: (
    <>
      <rect x="3" y="5" width="18" height="15" rx="1.5" />
      <path d="M7 5V3h10v2M7.5 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5.5 17c.3-1.5 1.1-2.2 2-2.2s1.7.7 2 2.2M13 10h5M13 14h5M13 17h3" />
    </>
  ),
  actions: (
    <>
      <path d="M9 4h6a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2Z" />
      <rect x="5" y="4" width="14" height="18" rx="1.5" />
      <path d="m8 13 2.5 2.5L16 10" />
    </>
  ),
  calls: (
    <>
      <path d="M4 5c0 8.2 6.8 15 15 15l1-4-4.5-2-2.2 2c-3-1.2-4.1-2.3-5.3-5.3l2-2.2L8 4Z" />
      <path d="M15 5h5M16 9h4M17 13h3" />
    </>
  ),
  agents: (
    <>
      <path d="M3 13v-1a9 9 0 0 1 18 0v1M4 12h3v7H6a2 2 0 0 1-2-2v-5ZM20 12h-3v7h1a2 2 0 0 0 2-2v-5ZM17 20a5 5 0 0 1-4 2h-2" />
    </>
  ),
  brokers: (
    <>
      <rect x="3" y="5" width="18" height="15" rx="1.5" />
      <circle cx="9" cy="11" r="2" />
      <path d="M5.8 17c.4-1.8 1.4-2.6 3.2-2.6s2.8.8 3.2 2.6M15 10h3M15 14h3M15 17h2" />
    </>
  ),
  emerging: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="1.5" />
      <path d="m6 16 4-4 3 3 5-7M15 8h3v3" />
    </>
  ),
}

export function NavIcon({ name }: { name: NavIconName }) {
  return (
    <svg
      className="nv2-navicon"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  )
}

export type { NavIconName }

