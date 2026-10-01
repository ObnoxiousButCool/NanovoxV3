/**
 * The action board's write path (Revised plan Phase 4, decision D6).
 *
 * Kept apart from `insights.ts`, which is read-only end to end: this is the
 * one file in the frontend that changes server state, so "does this ever
 * POST or PATCH" is answerable from the filename alone.
 *
 * There is no `localStorage` here, on purpose. The prototype kept edits in
 * the browser because it had no backend; this one does, and every mutation
 * — create, tick, move, assign, log, record — goes to the server and the
 * board is invalidated so the next read reflects it. A card that "moved" only
 * in this tab is worse than one that failed to move at all.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult } from '@tanstack/react-query'

import { getJson, patchJson, postJson } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ActionBoard = components['schemas']['ActionBoardResponse']
export type Lane = components['schemas']['LaneResponse']
export type Action = components['schemas']['ActionResponse']
export type CreateActionBody = components['schemas']['CreateActionBody']
export type UpdateActionBody = components['schemas']['UpdateActionBody']

/** Every action being worked, and the lanes to draw — from configuration,
 * never hardcoded here. A lifecycle change on the server is a new board on
 * the next fetch, not a frontend rebuild. */
const BOARD_KEY = ['insights', 'actionBoard'] as const

/**
 * The board, narrowed by the shared filter bar.
 *
 * `search` is the bar's own query string, sent to the server rather than
 * applied here. An action belongs to a filtered corpus either by citing one
 * of its calls or by naming one of its employers, and the first half is a
 * join the client cannot do: the board's actions carry call ids, not
 * employers or regions, and one seeded action cites 179 calls. Filtering
 * here was the bug once before — it matched on the employer reference
 * alone, which every seeded signal-wide action leaves null, so an account
 * board came back empty and the page reported that nothing had needed an
 * action.
 *
 * Before this the board was fetched unfiltered while the findings panel
 * beside it was not, so the two answered different questions under one bar.
 *
 * The search is part of the query key, so each scope is cached separately
 * and the mutations below still invalidate all of them: react-query matches
 * a query key by prefix.
 */
export function useActionBoard(search = '') {
  return useQuery({
    queryKey: search === '' ? BOARD_KEY : [...BOARD_KEY, search],
    queryFn: () =>
      getJson<ActionBoard>(
        search === '' ? '/insights/actions/board' : `/insights/actions/board?${search}`,
      ),
  })
}

/**
 * One action, by id, straight from the server.
 *
 * The board's own list is the usual source — it is invalidated after every
 * write, so a card reopened after a move already shows the new state. This
 * exists for the one moment that list cannot cover: right after a create,
 * before the invalidated board has refetched, there is nowhere else to read
 * the new card's detail from.
 */
export function useAction(id: number | null) {
  return useQuery({
    queryKey: ['insights', 'action', id],
    queryFn: () => getJson<Action>(`/insights/actions/${String(id)}`),
    enabled: id !== null,
  })
}

/** Raise an action, from a playbook or by hand. Refetches the board so the
 * new card appears where the server put it. */
export function useCreateAction(): UseMutationResult<Action, Error, CreateActionBody> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateActionBody) => postJson<Action>('/insights/actions', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BOARD_KEY })
    },
  })
}

/** Move, assign, tick, log, or record what was done and what changed. One
 * mutation for every write the card modal offers, because they are all the
 * same shape on the wire: an `UpdateActionBody` patch to one action. */
export function useUpdateAction(): UseMutationResult<
  Action,
  Error,
  { id: number; body: UpdateActionBody }
> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }) => patchJson<Action>(`/insights/actions/${String(id)}`, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BOARD_KEY })
    },
  })
}
