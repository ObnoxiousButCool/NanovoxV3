/**
 * The wire shapes the primitives render, aliased from the generated client.
 *
 * Aliased rather than redeclared. A hand-written copy of `FigureResponse`
 * would compile happily after the backend changed it, and the first sign of
 * the drift would be a figure rendering as `undefined` on a screen.
 */

import type { components } from '@/shared/api/schema'

export type Figure = components['schemas']['FigureResponse']
export type CodedValue = components['schemas']['CodedValue']
export type Scope = components['schemas']['ScopeResponse']
export type Period = components['schemas']['PeriodResponse']
