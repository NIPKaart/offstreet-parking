<!--
*** To avoid retyping too much info. Do a search and replace for the following:
*** github_username, repo_name
-->

<!-- Banner -->
![alt Banner of the offstreet parking project](assets/banner_offstreet_parking.png)

<!-- PROJECT SHIELDS -->
[![GitHub Activity][commits-shield]][commits]
[![GitHub Last Commit][last-commit-shield]][commits]
[![Linting][linting-shield]][linting-url]

![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE.md)
[![Contributors][contributors-shield]][contributors-url]

[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]

## About

Collect Amsterdam car garages and P+R for [NIPKaart][nipkaart], independently of core, as two separate streams through private R2:

| Stream | Issue | Content | Default cadence | Core consumer |
| --- | --- | --- | --- | --- |
| Catalog | [#656](https://github.com/NIPKaart/offstreet-parking/issues/656) | Identity, name, type, location, capacity | Daily | [core#1250](https://github.com/NIPKaart/core/issues/1250): intake, review, publication |
| Observations | [#657](https://github.com/NIPKaart/offstreet-parking/issues/657) | Dated free spaces, freshness, status | Every 2 minutes | [core#1221](https://github.com/NIPKaart/core/issues/1221): ordered live update, no review |

This repository implements only the collector side. Both formats are collector-side contract candidates until core accepts them.

## Development and source inspection

Use Python 3.14 and [uv](https://docs.astral.sh/uv/). Install and check the locked environment:

```bash
uv sync --locked --python 3.14
uv lock --check
uv run python -m unittest discover -s tests -v
uv run pre-commit run --all-files
```

`main.py` still defaults to offline help. Its finite `--fetch amsterdam` and `--fetch hamburg` commands only print source counts and never write data. Hamburg is not a catalog source: its package cannot yet preserve missing live counts and the existing 40-record inspection limit does not prove completeness. No core API/database credentials or `.env` loading are involved in local export or tests.

The Amsterdam package requires release 7.0.2 or newer within the 7.0 line, containing readable garage names, original `source_name` and current P+R classification from [package PR #1315](https://github.com/klaasnicolaas/python-odp-amsterdam/pull/1315). It also includes the 7.0.1 coordinate and vehicle fixes. Source HTTP/parsing remains in the universal package; the collector only selects car facilities and maps NIPKaart records. Boto3 uses the same S3 transport as the municipal collector.

## Local catalog export

```bash
uv run python export.py --city amsterdam --output /tmp/offstreet-amsterdam.json
```

The source is Amsterdam's [current garage availability feed](https://data.overheid.nl/dataset/9orkef6t-au29g), retrieved by `ODPAmsterdam.all_garages(vehicle="car")` from [the provider endpoint](https://p-info.vorin-amsterdam.nl/v1/ParkingLocation.json). The package reads one non-paginated response, excludes its named dummy/test facilities and selects cars. Facility category and vehicle type are package interpretations of source names, not verified accessibility claims. This is the complete car selection of that feed, not proof that every real Amsterdam garage is represented. A provider silently omitting a facility cannot be detected here; absence must remain a review decision in core.

One fetch has a 180-second deadline (the package also has a per-request timeout). Empty responses, duplicate/blank IDs, invalid names, invalid locations, invalid capacities or dates, more than 10,000 selected records and files over 32 MiB are rejected. Amsterdam coordinates must lie within latitude 52–53 and longitude 4–6; this guards against accidental axis reversal. Unknown capacity stays `null`; zero stays zero. A failed fetch or write leaves the previous output intact. The exporter fsyncs a temporary file and atomically renames it only after validation.

The `nipkaart-offstreet-catalog-1` envelope contains:

| Field | Meaning |
| --- | --- |
| `dataset` | `nl-amsterdam-garages`; identity namespace, independent of core database IDs |
| `selection` | `car-garages-and-pr` |
| `delivery_id` | New UUID for each successful collection; identical bytes/UUID reused for upload retries |
| `retrieved_at` | UTC time immediately before fetching, for future core ordering checks |
| `complete` | `true` only after the complete package selection has passed validation |
| `source_count` | Number of unique records in this selected catalog |
| `records` | Sorted by the original `external_id` |

Each record contains exactly these fields (illustrative values):

```json
{
  "external_id": "06757815-834C-0E44-42B0-AE4FC4AF9CEF",
  "name": "Byzantium",
  "source_name": "P-106_ Byzantium (opendata)",
  "facility_type": "garage",
  "geometry": {"type": "Point", "coordinates": [4.88001, 52.3619]},
  "short_stay": {"capacity": 446},
  "long_stay": null,
  "accessible": {"capacity": null},
  "source_observed_at": "2026-09-27T23:25:05Z"
}
```

`external_id` preserves the source `Id`, including case; a moved facility keeps that ID. `name` is the package-normalized display name; `source_name` preserves the original label. Technical prefixes and the trailing `(opendata)` label are removed, while meaningful numbers such as `P21` and `P4` and parentheses such as `(ACTA)` remain. `facility_type` is `garage` or `park_and_ride`. Coordinates are WGS84 **longitude, latitude**. Short/long-stay capacities are separate general counts: they are not added or inferred to be accessible. The source supplies no explicit reliable combined total and does not establish that the two categories are disjoint, so no combined total is inferred. `short_stay` is the primary visitor-parking group; `long_stay` represents the source category for season-ticket holders and is `null` when no capacity is supplied. This means no reported data, not proof that season-ticket parking is unsupported. For example, two category capacities of 110 must not silently become a claimed total of 220. The feed does not provide accessible capacity, so it stays `null` even when general capacity is zero.

`source_observed_at` preserves the package's source `PubDate` in UTC; it is an observation/publication timestamp and must not be treated as the modification date of catalog metadata. The source has no separate metadata modification timestamp, so the catalog does not emit one. A core metadata comparison should not treat a newer `source_observed_at` alone as a facility change. Free spaces, occupancy percentages, open/closed status and accessible availability are deliberately absent. Those belong to the separate observation stream below.

## Local live-observation export

```bash
uv run python export.py --city amsterdam --kind observations --max-age-seconds 300 --output /tmp/offstreet-amsterdam-live.json
```

This finite export writes the same file that the observation collector below uploads to R2.

The `nipkaart-offstreet-observations-1` envelope contains `dataset`, `selection`, a new `delivery_id`, UTC retrieval-start `fetched_at`, `max_age_seconds`, `source_count` and records sorted by the same original `external_id` as the catalog. Join the two files on `dataset` and `external_id`. Observation absence never means deleting a facility.

Example observation (illustrative counts):

```json
{
  "external_id": "06757815-834C-0E44-42B0-AE4FC4AF9CEF",
  "observed_at": "2026-09-27T23:49:05Z",
  "valid_until": "2026-09-27T23:54:05Z",
  "status": "current",
  "source_state": "ok",
  "short_stay": {"capacity": 446, "available": 391},
  "long_stay": null,
  "accessible": {"capacity": null, "available": null}
}
```

`short_stay` groups the visitor capacity and available spaces together. The optional `long_stay` uses the same shape for season-ticket holders: for example `{"capacity": 40, "available": 12}`. It is `null` only when the source supplies neither long-stay capacity nor free spaces; partial data and zero remain visible. Each group distinguishes unknown (`null`) from zero. The catalog uses the same group names with `capacity` only; observations add `available`, freshness and status. Capacity is repeated here so a consumer can interpret the count without re-reading the catalog, but the catalog remains the reviewed capacity claim. General free spaces never imply free accessible spaces, and the groups are never summed into an unverified total.

`current` requires source state `ok` and a source timestamp at or before retrieval start, strictly less than the configured maximum age. Exactly at expiry the record is `stale`: counts remain dated historical observations, not current availability. A missing/future timestamp or non-`ok` source state is `unavailable` and suppresses free-space counts. `unavailable` describes unusable observation data, not a claim that the garage is closed. `valid_until` is computed from source time, never retrieval time; consumers must check this timestamp again when reading a file because an exported `current` label ages. The default five minutes follows the measured source timing below; core#1221 still has to accept it as the production freshness policy.

The export uses the same complete car selection, validation, fetch deadline, 10,000-record/32 MiB limits and atomic file completion as the catalog. Invalid or partial retrieval cannot replace the previous file. Names and coordinates belong to the catalog; live records carry source identity and dated counts only.

## Private R2 delivery

Configure the environment from `.env.example` for a **dedicated private offstreet staging bucket**. Leave public access disabled. The collector requires an Object Read & Write token scoped only to that bucket; it reads an existing object after a conditional-create conflict to verify the exact bytes. The future core consumer must have a separate read-only identity. Standard R2 tokens are bucket-scoped, so the key prefix is an organization convention, not a permission boundary. See [R2 token permissions](https://developers.cloudflare.com/r2/api/tokens/).

```bash
# After setting R2_ENDPOINT, R2_BUCKET, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
uv run --env-file .env python collector.py --city amsterdam --directory /tmp/offstreet-deliveries
```

The finite collector persists `<directory>/nl-amsterdam-garages/pending.json` before upload and acquires a nonblocking per-dataset lock. Each completed delivery is one `PutObject` at `offstreet/nl-amsterdam-garages/<delivery_id>.json`, with `If-None-Match: *`, a SHA-256 request checksum and SHA-256 metadata. There is no separate manifest or partially visible multipart delivery. R2 supports [conditional S3 operations](https://developers.cloudflare.com/r2/api/s3/api/) and [SHA-256 PutObject checksums](https://developers.cloudflare.com/r2/platform/release-notes/#2023-06-16).

Observations use the same command with `--kind observations` and their own state directory, `<directory>/nl-amsterdam-garages/observations/`:

```bash
uv run --env-file .env python collector.py --city amsterdam --kind observations --max-age-seconds 300 --directory /tmp/offstreet-deliveries
```

Each observation delivery is one object at `offstreet-observations/nl-amsterdam-garages/<fetched_at>-<delivery_id>.json`, where `<fetched_at>` is UTC `YYYYMMDDTHHMMSSZ`. Keys therefore list in retrieval order, and the separate prefix keeps catalog discovery from ever seeing live files. The upload uses the same conditional create, checksums and byte comparison as the catalog.

On a catalog timeout or upload failure, retain `pending.json` and retry exactly that artifact before fetching again. An already-existing object is accepted only if its downloaded bytes match; a conflict leaves the pending file for diagnosis. Only acknowledged delivery moves it to `last.json`. Both renames are followed by directory fsync. Do not edit a pending file or delete the persistent volume to recover a failure. The collector never deletes remote objects or writes core data.

A pending observation file is retried the same way while it is still fresh. Once `fetched_at + max_age_seconds` has passed, it is discarded locally and replaced by a new retrieval, so an outage never produces a backlog of late uploads. A failed fetch writes no pending file and uploads nothing.

### Retention

Catalog objects stay until core has verified intake and replay. Observation objects are only useful until they expire, so give the observation prefix its own R2 lifecycle rule. Seven days leaves room to debug core intake:

```bash
npx wrangler r2 bucket lifecycle add <bucket> expire-offstreet-observations offstreet-observations/ --expire-days 7
```

Never apply that rule to `offstreet/`. At two-minute intervals the observation prefix holds about 5,000 small objects per week.

## Scheduling

The provided Compose configuration is opt-in and does not replace any existing deployment:

```bash
docker compose build
# Start only against the separately configured staging bucket:
docker compose up -d
```

Compose runs two independent services on one persistent volume:

- `collector` delivers the catalog immediately, then every `COLLECTOR_INTERVAL_SECONDS` (default 86,400) after success, with retries after at most 300 seconds and a 300-second child deadline.
- `observations` delivers observations immediately, then every `OBSERVATION_INTERVAL_SECONDS` (default 120), with a 90-second child deadline and `OBSERVATION_MAX_AGE_SECONDS` (default 300) as freshness.

Each service holds its own scheduler lock and each stream its own per-dataset delivery lock, so a slow catalog run never delays live counts. SIGTERM stops the child before exit. The volume retains pending/last files across restarts. Existing jobs and legacy data remain unchanged.

On 2026-09-28 the Amsterdam feed returned 47 observations with a median age of about 40 seconds (17 seconds to 5 minutes), so the source refreshes roughly every minute. A two-minute poll with five-minute freshness keeps counts current without chasing every source update. Repeat this measurement at different times of day before production acceptance.

## Validation evidence and remaining acceptance

On 2026-09-28 (Europe/Amsterdam), the corrected package exported 47 car facilities with 47 unique source IDs. Coordinates ranged from latitude 52.3078–52.403327 and longitude 4.83811–4.969892532348648. All 47 accessible capacities remained unknown. The original 7.0.0 package failed location validation on the current latitude-first feed and classified `FP-` bicycle facilities as cars; the package fix covers current and historic axis orders and prefixes.

All 42 collector tests and code checks passed locally. A subsequent paired catalog/live export returned the same 47 source IDs, including 10 P+R facilities; the live snapshot held 44 current observations and three unavailable observations. The Docker image built successfully, ran its help commands without network access and repeated the live export with the same 47 facility IDs and a new delivery UUID. The naming package has 82 passing tests, including public vehicle-filter checks and current/legacy name cases.

A later dry run of both `collector.py` streams against the real source, with a stubbed bucket client, produced a capacity-only catalog and 47 observations (43 current, 4 unavailable) under their separate keys and state directories.

Offline tests cover small package-object mappings, source/size/completeness failures, stable IDs across exports, atomic output, immutable upload retries, conflicting bytes, observation expiry and stream separation, scheduling, timeouts and shutdown. Botocore request validation substitutes for a live bucket in those tests. Passing tests or a local export do not prove R2 credentials, deployment or core compatibility.

Still required with core#1221: accept the observation format, freshness and cadence; consume `offstreet-observations/` in key order; prove fresh/stale/unavailable display, late and duplicate arrivals, unknown facilities and no accessible-availability claims.

Still required with core#1250: approve the format revision; exercise actual private R2 upload/readback and scoped credentials; prove first intake and reimport, stable detail/favorite references, ordering/conflict rejection, missing-record review and authorized publication. Production activation, source publication rights/attribution confirmation, retention and any legacy handover remain separate acceptance decisions.

## Contributing

Would you like to contribute to the development of this project? Then read the prepared [contribution guidelines](CONTRIBUTING.md) and go ahead!

Thank you for being involved! :heart_eyes:

## License

MIT License

Copyright (c) 2021-2024 Klaas Schoute

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[nipkaart]: https://nipkaart.nl

<!-- MARKDOWN LINKS & IMAGES -->
[maintenance-shield]: https://img.shields.io/maintenance/yes/2024.svg
[contributors-shield]: https://img.shields.io/github/contributors/nipkaart/offstreet-parking.svg
[contributors-url]: https://github.com/nipkaart/offstreet-parking/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/nipkaart/offstreet-parking.svg
[forks-url]: https://github.com/nipkaart/offstreet-parking/network/members
[stars-shield]: https://img.shields.io/github/stars/nipkaart/offstreet-parking.svg
[stars-url]: https://github.com/nipkaart/offstreet-parking/stargazers
[issues-shield]: https://img.shields.io/github/issues/nipkaart/offstreet-parking.svg
[issues-url]: https://github.com/nipkaart/offstreet-parking/issues
[license-shield]: https://img.shields.io/github/license/nipkaart/offstreet-parking.svg
[commits-shield]: https://img.shields.io/github/commit-activity/y/nipkaart/offstreet-parking.svg
[commits]: https://github.com/nipkaart/offstreet-parking/commits/main
[last-commit-shield]: https://img.shields.io/github/last-commit/nipkaart/offstreet-parking.svg
[linting-shield]: https://github.com/NIPKaart/offstreet-parking/actions/workflows/linting.yaml/badge.svg
[linting-url]: https://github.com/NIPKaart/offstreet-parking/actions/workflows/linting.yaml

[pre-commit]: https://pre-commit.com
