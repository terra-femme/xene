import { useQuery } from '@tanstack/react-query'
import { fetchTwitchStatus } from '../lib/api'

/**
 * Polls Twitch live status for a list of artist logins every 2 minutes.
 * Returns a Map<twitch_login, stream_object> for fast O(1) artist lookup.
 * Only live channels appear in the map — offline artists are absent.
 */
export function useTwitchStatus(artists = []) {
  const logins = artists.map(a => a.twitch_login).filter(Boolean)

  const { data = [] } = useQuery({
    queryKey: ['twitch-live', logins],
    queryFn: () => fetchTwitchStatus(logins),
    enabled: logins.length > 0,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  })

  const liveMap = new Map(data.map(stream => [stream.twitch_login, stream]))
  console.log('[useTwitchStatus] live artists=', [...liveMap.keys()])
  return liveMap
}
