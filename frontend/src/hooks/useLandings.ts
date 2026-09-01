import { useCallback, useEffect, useState } from 'react'
import { getLandings } from '../api/client'
import type { Landing, PaginatedResponse } from '../types'

export function useLandings(initialPage = 1) {
  const [data, setData] = useState<PaginatedResponse<Landing> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(initialPage)
  const [search, setSearch] = useState('')
  const [mine, setMine] = useState(false)

  const fetchLandings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getLandings(page, 12, search, mine)
      setData(result)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || (err instanceof Error ? err.message : 'Failed to load landings'))
    } finally {
      setLoading(false)
    }
  }, [page, search, mine])

  useEffect(() => {
    fetchLandings()
  }, [fetchLandings])

  return { data, loading, error, page, setPage, search, setSearch, mine, setMine, refetch: fetchLandings }
}
