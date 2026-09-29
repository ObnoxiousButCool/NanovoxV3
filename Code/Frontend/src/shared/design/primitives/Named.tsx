/**
 * A person or an account, as `Name (REF)`.
 *
 * One component for every surface that shows a caller, an agent or an
 * employer, because this is a format and not a rendering choice: four
 * screens each writing `name ?? ref` their own way is four places for the
 * brackets to go missing, and the reference is what makes the name
 * checkable.
 *
 * ## The reference never leaves
 *
 * It is what a support ticket, a filter parameter and the export all speak,
 * and two members can share a name. So the name is put in front of it
 * rather than in place of it, and when reference data does not know the
 * person the reference stands alone — **never a blank, and never a
 * name-shaped placeholder**. A row reading "Unknown" would say we could not
 * identify the caller; the truth is that the sheets do not carry them,
 * which is a gap in reference data rather than an anonymous call.
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
  fallback = 'Not recorded',
}: {
  name?: string | null | undefined
  reference?: string | null | undefined
  /** Shown when there is neither a name nor a reference. */
  fallback?: string
}) {
  if (reference === null || reference === undefined || reference === '') {
    return name === null || name === undefined || name === '' ? (
      <span className="nv-none">{fallback}</span>
    ) : (
      <>{name}</>
    )
  }
  if (name === null || name === undefined || name === '') {
    return <span className="nv-ref">{reference}</span>
  }
  return (
    <>
      {name} <span className="nv-ref">({reference})</span>
    </>
  )
}
