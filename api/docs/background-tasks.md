# Background Tasks

Everything that runs behind the request/response lifecycle: the three cron loops and graceful-shutdown ordering.

## Lifecycle Owner

All tasks are `asyncio.create_task(...)` started in `main.py` `_startup()` and cancelled in `_shutdown()`. Cancellation is ordered to stop data loss:

```
2s drain → cancel product_ai_cron / embedding_cron / activity_cleanup
        → drain_activity_tasks() (flush in-flight activity writes)
        → ws_manager.close() (close tracked sockets)
        (then) AI client → mongo → broker → redis → engine
```

Each task loops on `while not shutdown_event.is_set()`; cancellation propagates through awaits (they don't swallow `CancelledError`), so cycles stop cleanly mid-iteration.

## 1. AI Description Cron (`product_ai_cron`)

| Constant | Value |
|---|---|
| Redis lock key | `cron:product_ai_generation` |
| Lock TTL | 600s (`NX EX`) |
| Cycle interval | 300s |
| Cycle timeout | 300s |
| Batch size | 10 |
| Retries | 3 (`1s/3s/9s` backoff) |

**Cycle**: (1) `SET lock NX EX 600` — if held elsewhere, skip. (2) Check `product_ai_generation_cron` system setting == `"true"`. (3) Resolve `default_llm_model`. (4) Query products missing `ai_description_en` **and** `ai_description_ar` (batch of 10). (5) Per product: `get_product_info` → minified JSON → `pre_prompt + data + ending_prompt` → `generate_description` → save `AIDescriptionVersion` + update product. (6) Write one `activity_logs` row (`CRON_RUN`, products in details). (7) Release lock.

The lock makes the cron **single-runner across replicas** (TTL > cycle guarantees no double processing). Lock release is not a blind `DEL`: it uses the owner-token compare-and-del Lua script in `core/distributed_lock.py`, so an expired-and-reacquired lock can never be released by the previous owner. Manual run: `uv run scripts/run_cron.py` (one cycle, foreground, same code path).

## 2. Embedding Recovery Cron (`embedding_cron`)

| Constant | Value |
|---|---|
| Cycle interval | 60s |
| Distributed lock | `cron:embedding_recovery` (TTL 600s) |
| Stale threshold | 2 minutes |
| Batch size | 50 |

Finds `product_embeddings` rows for the **active model** with `embedding_status IN (pending, generating, error)` whose `updated_at < now − 2min` (the 2-min grace protects in-flight embeddings) and re-submits them via `embed_product(..., webhook_url=...)`. Missing rows for the active model are inserted first (`_ensure_active_model_rows`). Build failure → row status `error` + reason. Writes a `CRON_RUN` activity row per cycle. See [Embedding Pipeline](embedding-pipeline.md).

- **Own distributed lock**: the cron takes `cron:embedding_recovery` (`SET NX EX`, TTL 600s) so only one replica submits per cycle.
- **Atomic row claiming**: `_claim_embedding_row` / `ProductEmbeddingRepository.claim_row` flips a row to `generating` in a single atomic update — concurrent cron/backfill runs cannot double-submit the same row; the stale cutoff prevents re-submitting rows another worker just picked up.
- **Webhook URL**: `build_webhook_url()` appends `?token=<webhook_secret>` to `api_base_url + /api/v1/webhook/embedding-result` when a secret is configured.

## 3. Activity Log Cleanup (`activity_log_cleanup`)

Every 24h: `DELETE FROM activity_logs WHERE created_at < now() − interval '60 days'` (single batched statement, logged). Also runs **once immediately at startup** before entering the loop. See [Logging](logging.md).

## 4. Startup Order in `main.py`

```
logging → redis → postgres engine (pool 10, overflow 20, pool_pre_ping)
  → broker (30s connect timeout, degraded mode on failure)
  → AI client → ws_manager → Mongo (optional, disables chat when unset)
  → MinIO (4 buckets ensured: product-graph, temp-files, profile-photos, store-photos)
  → background tasks (product_ai_cron, embedding_cron, activity_cleanup) → READY
```

`/ready` reports `ok` only when db, redis, rabbitmq, and ai-engine all pass their health checks.

## Failure Semantics

- Every task is wrapped so an unexpected exception is logged (with stack) and the loop **continues** on the next cycle — one bad product never kills the cycle.
- Infra outages (RabbitMQ, MinIO, engine) put the app in **degraded mode**: requests that need the unavailable dependency return 5xx (`SERVICE_UNAVAILABLE`), everything else keeps working.
