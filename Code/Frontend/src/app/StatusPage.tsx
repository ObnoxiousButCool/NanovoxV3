import { useHealth } from '@/shared/api/queries'

export function StatusPage() {
  const { data, isPending, isError, error } = useHealth()

  return (
    <main>
      <h1>NanoVox Insights</h1>
      {isPending && <p>Checking the API…</p>}
      {isError && <p role="alert">Could not reach the API: {error.message}</p>}
      {data && (
        <p>
          API status: <strong>{data.status}</strong> ({data.application} {data.version},{' '}
          {data.environment})
        </p>
      )}
    </main>
  )
}
