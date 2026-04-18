import { useQuery } from '@tanstack/react-query'
import { fetchFeed } from '../lib/api'

export function useFeed(artistId = null) {
  return useQuery({
    queryKey: ['feed', artistId],
    queryFn: () => fetchFeed({ artistId }),
    staleTime: 5 * 60 * 1000,        // treat data as fresh for 5 min
    refetchInterval: 10 * 60 * 1000, // silently re-fetch every 10 min while app is open
    refetchOnWindowFocus: false,      // don't blast APIs on every tab switch
    refetchOnMount: false,
  })
}
