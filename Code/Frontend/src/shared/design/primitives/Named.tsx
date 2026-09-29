/**
 * A person or an account, as `Name (REF)`.
 *
 * One component for every surface that shows a caller, an agent or an
 * employer, because this is a format and not a rendering choice: four
 * screens each writing `name ?? ref` their own way is four places for the
 * brackets to go missing, and the reference is what makes the name
 * checkable.
 *
 * ## The reference stays, except on a caller
 *
 * For an agent or an employer the reference is what a support ticket, a
 * filter parameter and the export all speak, and two people can share a
 * name — so the name goes in front of it rather than in place of it.
 *
 * **A caller is different: `mask` drops their reference from the screen.**
 * Ranjit asked for the member id masked on 2026-09-29. Member and contact
 * references are the one identifier on these screens that points at a
 * person outside the business rather than at a colleague or an account.
 *
 * The exception is a caller reference data does not know. There the
 * reference is shown, because the alternative is a row identifying nobody
 * at all — **never a blank, and never a name-shaped placeholder**. A row
 * reading "Unknown" would say we could not identify the caller; the truth
 * is that the sheets do not carry them, which is a gap in reference data
 * rather than an anonymous call.
 *
 * ## Why names are shown here at all
 *
 * The evidence drawer and the workbench carried references only, and said
 * so in their own comments. Ranjit asked for names across the application
 * on 2026-09-29. The **CSV export is deliberately not changed**: a file
 * leaves the application and gets mailed around, and `calls.py` settles
 * that separately — a name on a screen behind the product is a different
 * exposure from a name in a spreadsheet in somebody's inbox.
 */

export function Named({
  name,
  reference,
  mask = false,
  fallback = 'Not recorded',
}: {
  name?: string | null | undefined
  reference?: string | null | undefined
  /**
   * Keep the reference off the screen once the name is known. Set on
   * callers, whose reference points at a member or a contact.
   */
  mask?: boolean
  /** Shown when there is neither a name nor a reference. */
  fallback?: string
}) {
  const named = name !== null && name !== undefined && name !== ''
  const referenced = reference !== null && reference !== undefined && reference !== ''

  if (!named) {
    // Masked or not, a caller with no name falls back to the reference:
    // the alternative identifies nobody, and the reference is all that is
    // left to tie the row to a call.
    return referenced ? (
      <span className="nv-ref">{reference}</span>
    ) : (
      <span className="nv-none">{fallback}</span>
    )
  }
  if (mask || !referenced) return <>{name}</>
  return (
    <>
      {name} <span className="nv-ref">({reference})</span>
    </>
  )
}
