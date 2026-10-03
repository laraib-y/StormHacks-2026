# DineOff architecture

DineOff is one Next.js app and one FastAPI app. They run as separate processes. There is no Docker, message bus, or extra service.

```text
Browser
  |  HTTP + WebSocket
  v
FastAPI
  |-- AIService -------- GeminiAIService or MockAIService
  |-- RestaurantProvider  GeoapifyRestaurantProvider or MockRestaurantProvider
  |-- SessionService
  |-- MatchingService
  v
MySQL or TiDB Cloud
```

## Request path

1. The host describes dinner. `SessionService` asks `AIService` for a `DinnerIntent`.
2. Pydantic validates that intent. The raw model text is never interpolated into SQL.
3. `RestaurantProvider` returns about 12 normalized restaurants. They are stored once and linked to the session in a stable order.
4. Friends join with a room code and a nickname. There are no accounts.
5. The host starts the dinner. Connected browsers receive `dinner_started` and open the same deck.
6. Swipes are private. The socket only broadcasts how many people have finished.
7. When everyone has swiped every restaurant, `MatchingService` ranks the deck and the room receives `results_ready`.

## Service boundaries

`AIService`

- `GeminiAIService` calls Gemini and validates JSON into `DinnerIntent`.
- `MockAIService` is a deterministic keyword parser.
- If the Gemini key is missing, or the call fails, the mock parser is used.

`RestaurantProvider`

- `GeoapifyRestaurantProvider` geocodes the location, loads places, and normalizes them into `Restaurant`.
- `MockRestaurantProvider` returns a curated deck.
- A missing key, a failed request, or a short result list falls back to mock data.
- The Geoapify key stays on the server.

`MatchingService`

- `compatibility = likes / total participants`
- Sort by compatibility, then likes, then rating, then name.
- The function is isolated so later fairness or travel-time rules can replace it without changing the API.

## Realtime

`/ws/sessions/{room_code}` sends:

- `state`
- `participant_joined`
- `participant_left`
- `dinner_started`
- `swipe_progress`
- `all_completed`
- `results_ready`

Progress messages contain counts only. They do not say who liked which restaurant.

## Data model

- `sessions` holds the room, description, host, and status (`lobby`, `active`, `completed`).
- `participants` belong to one session.
- `restaurants` stores normalized places. The same external place can be reused.
- `session_restaurants` attaches one ordered deck to a session. This join table is what keeps swipe order identical for the group.
- `swipes` stores `like` or `pass`, with a unique constraint on session, participant, and restaurant.

`host_participant_id` is stored on the session and checked in the service. It is not a database foreign key, because the session and its host row are created together.

## Intentionally not built

Vetoes, super-likes, accounts, payments, notifications, vector search, taste memory, travel-time routing, and ElevenLabs are extension points only. They are not part of this MVP.
