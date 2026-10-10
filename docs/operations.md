# Operations

How the collector runs and delivers. The formats are in [formats.md](formats.md).

## Scheduling

```bash
docker compose up -d
```

`compose.yaml` runs two independent services on one volume. Each has its own lock and a deadline for each run:

- `collector`: Amsterdam and Hamburg catalogs, every `COLLECTOR_INTERVAL_SECONDS` (default 86,400); retries after at most 5 minutes.
- `observations`: Amsterdam and Hamburg observations, every `OBSERVATION_INTERVAL_SECONDS` (default 120).

Each scheduler starts one finite command per registered city, with a separate retry deadline per dataset and a shared-volume lock per stream. Catalog pending/last files remain under their dataset folders; Amsterdam's existing paths stay intact. A failed Hamburg command does not prevent the scheduler from trying Amsterdam and cannot replace its pending catalog.

On 2026-09-28 the source's observations had a median age of ~40 seconds (range 17 seconds to 5 minutes), so the feed refreshes about once a minute. Existing jobs and legacy data are not touched.

## R2 delivery

Deliver to the existing private EU bucket `nipkaart-imports`, next to the municipal collector's `municipal/` prefix. Reuse the municipal collector's R2 token (Object Read & Write, scoped to that bucket) and enter it in `.env` (see `.env.example`). The collector itself never overwrites or deletes objects. Core reads with its existing credentials.

```bash
uv run --env-file .env python collector.py --city amsterdam --directory /tmp/offstreet
uv run --env-file .env python collector.py --city amsterdam --kind observations
```

Every upload is one `PutObject` with `If-None-Match: *` and a SHA-256 checksum. If the object already exists, the upload only succeeds when the remote bytes are identical. The collector never deletes or overwrites objects.

- **Catalog:** first saved as `<directory>/nl-amsterdam-garages/pending.json`. After a failure, that same file is retried before anything new is fetched, and it moves to `last.json` once it is delivered. Do not edit or delete the pending file to recover.
- **Observations:** fetched and uploaded straight away, with no local state. A failure delivers nothing; the next run two minutes later is newer anyway.

## Retention

Set these two lifecycle rules on `nipkaart-imports` once, before the first delivery:

| Rule name | Prefix | Delete after | Why |
| --- | --- | --- | --- |
| `expire-offstreet-catalog` | `offstreet/` | 30 days | Well beyond the 7-day core outage window, same as `municipal/` |
| `expire-offstreet-observations` | `offstreet-observations/` | 7 days | Outdated within minutes; kept only for debugging |

The trailing slash matters: `offstreet/` does not match `offstreet-observations/`. Never add a rule without a prefix, because it would also delete municipal deliveries.

**Dashboard:** R2 → `nipkaart-imports` → Settings → Object lifecycle rules → Add rule. Enter the name and prefix, choose to delete objects after the number of days in the table, and save. Repeat for the second rule.

**Or with Wrangler** (after `npx wrangler login`; the bucket is in the EU jurisdiction):

```bash
npx wrangler r2 bucket lifecycle add nipkaart-imports expire-offstreet-catalog offstreet/ --expire-days 30 --jurisdiction eu
npx wrangler r2 bucket lifecycle add nipkaart-imports expire-offstreet-observations offstreet-observations/ --expire-days 7 --jurisdiction eu
npx wrangler r2 bucket lifecycle list nipkaart-imports --jurisdiction eu
```

The list should show both offstreet rules plus the municipal rule (`municipal/`, 30 days) from [disabled-parking](https://github.com/NIPKaart/disabled-parking#retention).

## Local export

Write one delivery to a file without R2 or core. A failed export keeps the previous file intact.

```bash
uv run python export.py --city amsterdam --output /tmp/catalog.json
uv run python export.py --city amsterdam --kind observations --output /tmp/observations.json
uv run python export.py --city hamburg --output /tmp/hamburg-catalog.json
uv run python export.py --city hamburg --kind observations --output /tmp/hamburg-observations.json
```
