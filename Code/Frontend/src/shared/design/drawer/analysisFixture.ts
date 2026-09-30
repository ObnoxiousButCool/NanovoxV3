/**
 * A call nothing has run on, as the API returns it.
 *
 * `analysis` is required on the evidence response — a call the pipeline has
 * not touched still gets four panels saying so, because "nothing has run" is
 * the answer to what we know about it. So a stub that omits the field is not
 * a smaller version of the real response; it is a shape the server cannot
 * produce, and a component written against it would be written against
 * nothing.
 *
 * Shared rather than copied into each test file for the reason the endpoint
 * owns its own column list: three copies of this drift, and the one that
 * drifts is the one nobody re-reads.
 */

import type { components } from '@/shared/api/schema'

const NOT_RUN = 'The pipeline has not run on this call yet.'
const NOT_RUN_OPTIONAL =
  'This layer has not run on this call. It is not required for a call to have ' +
  'an analysis, so the other panels still stand.'

export function unrunAnalysis(
  callerRef: string,
): components['schemas']['CallAnalysisResponse'] {
  return {
    l1: { ran: false, notRunBecause: NOT_RUN, callerRef, controlExceptions: [] },
    l2: { ran: false, notRunBecause: NOT_RUN },
    l3: { ran: false, notRunBecause: NOT_RUN_OPTIONAL },
    l4: { ran: false, notRunBecause: NOT_RUN_OPTIONAL },
  }
}
