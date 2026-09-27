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

Prepare one complete Amsterdam car-garage/P+R catalog for [NIPKaart][nipkaart], independently of core. Issue [#656](https://github.com/NIPKaart/offstreet-parking/issues/656) delivers catalog metadata through private R2; [core#1250](https://github.com/NIPKaart/core/issues/1250) owns intake, review and publication. This revision implements only the collector, including a separate local observation export for [#657](https://github.com/NIPKaart/offstreet-parking/issues/657). The format below is a collector-side contract candidate until verified with core; this does not close #656.

## Development and source inspection

Use Python 3.14 and [uv](https://docs.astral.sh/uv/). Install and check the locked environment:

```bash
uv sync --locked --python 3.14
uv lock --check
uv run python -m unittest discover -s tests -v
uv run pre-commit run --all-files
```

`main.py` still defaults to offline help. Its finite `--fetch amsterdam` and `--fetch hamburg` commands only print source counts and never write data. Hamburg is not a catalog source: its package cannot yet preserve missing live counts and the existing 40-record inspection limit does not prove completeness. No core API/database credentials or `.env` loading are involved in local export or tests.

The Amsterdam package is temporarily pinned to immutable commit `aed3b0b276d7e296955f34f09e1395cd150444d5` from [package PR #1315](https://github.com/klaasnicolaas/python-odp-amsterdam/pull/1315), containing readable garage names, original `source_name` and current P+R classification. It also includes the released 7.0.1 coordinate and vehicle fixes. Replace this pin with a published release containing #1315 before merging the collector PR. Source HTTP/parsing remains in the universal package; the collector only selects car facilities and maps NIPKaart records. Boto3 uses the same S3 transport as the municipal collector.

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
  "capacity": {
    "general_total": null,
    "general_short_stay": 446,
    "general_long_stay": null,
    "accessible": null
  },
  "metadata_updated_at": null,
  "source_observed_at": "2026-09-27T23:25:05Z"
}
```

`external_id` preserves the source `Id`, including case; a moved facility keeps that ID. `name` is the package-normalized display name; `source_name` preserves the original label. Technical prefixes and the trailing `(opendata)` label are removed, while meaningful numbers such as `P21` and `P4` and parentheses such as `(ACTA)` remain. `facility_type` is `garage` or `park_and_ride`. Coordinates are WGS84 **longitude, latitude**. Short/long-stay capacities are separate general counts: they are not added or inferred to be accessible. The source supplies no explicit reliable total and does not establish that the two categories are disjoint, so `general_total` stays `null`. For example, two category capacities of 110 must not silently become a claimed total of 220. The feed does not provide accessible capacity, so it stays `null` even when general capacity is zero.

`source_observed_at` preserves the package's source `PubDate` in UTC; it is an observation/publication timestamp and must not be treated as the modification date of catalog metadata. `metadata_updated_at` is unknown. A core metadata comparison should not treat a newer `source_observed_at` alone as a facility change. Free spaces, occupancy percentages, open/closed status and accessible availability are deliberately absent. Those observations are available through the separate local export below.

## Local live-observation export

```bash
uv run python export.py --city amsterdam --kind observations --max-age-seconds 300 --output /tmp/offstreet-amsterdam-live.json
```

This is a finite, manually invoked export for #657. The R2 collector and daily scheduler still accept only catalogs; this does not enable periodic live polling, upload or core intake.

The `nipkaart-offstreet-observations-1` envelope contains `dataset`, `selection`, a new `delivery_id`, UTC retrieval-start `fetched_at`, `max_age_seconds`, `source_count` and records sorted by the same original `external_id` as the catalog. Join the two files on `dataset` and `external_id`. Observation absence never means deleting a facility.

Example observation (illustrative counts):

```json
{
  "external_id": "06757815-834C-0E44-42B0-AE4FC4AF9CEF",
  "observed_at": "2026-09-27T23:49:05Z",
  "valid_until": "2026-09-27T23:54:05Z",
  "status": "current",
  "source_state": "ok",
  "capacity": {"general_total": null, "general_short_stay": 446, "general_long_stay": null, "accessible": null},
  "availability": {"general_total": null, "general_short_stay": 391, "general_long_stay": null, "accessible": null}
}
```

`capacity` holds source capacity; `availability` holds source free spaces. Both distinguish unknown (`null`) from zero. Totals remain unknown rather than summing unverified categories. General free spaces never imply free accessible spaces.

`current` requires source state `ok` and a source timestamp at or before retrieval start, strictly less than the configured maximum age. Exactly at expiry the record is `stale`: counts remain dated historical observations, not current availability. A missing/future timestamp or non-`ok` source state is `unavailable` and suppresses free-space counts. `unavailable` describes unusable observation data, not a claim that the garage is closed. `valid_until` is computed from source time, never retrieval time; consumers must check this timestamp again when reading a file because an exported `current` label ages. The default five minutes is a configurable local-test policy, not an approved production cadence/freshness agreement.

The export uses the same complete car selection, validation, fetch deadline, 10,000-record/32 MiB limits and atomic file completion as the catalog. Invalid or partial retrieval cannot replace the previous file. Names and coordinates belong to the catalog; live records carry source identity and dated counts only.

## Private R2 delivery and scheduling

Configure the environment from `.env.example` for a **dedicated private offstreet staging bucket**. Leave public access disabled. The collector requires an Object Read & Write token scoped only to that bucket; it reads an existing object after a conditional-create conflict to verify the exact bytes. The future core consumer must have a separate read-only identity. Standard R2 tokens are bucket-scoped, so the key prefix is an organization convention, not a permission boundary. See [R2 token permissions](https://developers.cloudflare.com/r2/api/tokens/).

```bash
# After setting R2_ENDPOINT, R2_BUCKET, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
uv run --env-file .env python collector.py --city amsterdam --directory /tmp/offstreet-deliveries
```

The finite collector persists `<directory>/nl-amsterdam-garages/pending.json` before upload and acquires a nonblocking per-dataset lock. Each completed delivery is one `PutObject` at `offstreet/nl-amsterdam-garages/<delivery_id>.json`, with `If-None-Match: *`, a SHA-256 request checksum and SHA-256 metadata. There is no separate manifest or partially visible multipart delivery. R2 supports [conditional S3 operations](https://developers.cloudflare.com/r2/api/s3/api/) and [SHA-256 PutObject checksums](https://developers.cloudflare.com/r2/platform/release-notes/#2023-06-16).

On a timeout or upload failure, retain `pending.json` and retry exactly that artifact before fetching again. An already-existing object is accepted only if its downloaded bytes match; a conflict leaves the pending file for diagnosis. Only acknowledged delivery moves it to `last.json`. Both renames are followed by directory fsync. Do not edit a pending file or delete the persistent volume to recover a failure. The collector never deletes remote objects or writes core data.

The provided Compose configuration is opt-in and does not replace any existing deployment:

```bash
docker compose build
# Start only against the separately configured staging bucket:
docker compose up -d
```

One serial scheduler runs immediately, then every 86,400 seconds after success, with retries after at most 300 seconds and a 300-second child deadline. A shared-volume lock prevents overlapping schedulers. SIGTERM stops the child before exit. The volume retains pending/last files across restarts. The default catalog cadence is daily; no live occupancy polling is enabled. Keep staging objects until core has verified intake/replay; agree retention and lifecycle rules before unattended production operation rather than expiring unconsumed deliveries. Existing jobs and legacy data remain unchanged.

## Validation evidence and remaining acceptance

On 2026-09-28 (Europe/Amsterdam), the corrected package exported 47 car facilities with 47 unique source IDs. Coordinates ranged from latitude 52.3078–52.403327 and longitude 4.83811–4.969892532348648. All 47 accessible capacities remained unknown. The original 7.0.0 package failed location validation on the current latitude-first feed and classified `FP-` bicycle facilities as cars; the package fix covers current and historic axis orders and prefixes.

All 34 collector tests and code checks passed locally. A subsequent paired catalog/live export returned the same 47 source IDs, including 10 P+R facilities; the live snapshot held 44 current observations and three unavailable observations. The Docker image built successfully, ran its help commands without network access and repeated the live export with the same 47 facility IDs and a new delivery UUID. The naming package has 82 passing tests, including public vehicle-filter checks and current/legacy name cases.

Offline tests cover small package-object mappings, source/size/completeness failures, stable IDs across exports, atomic output, immutable upload retries, conflicting bytes, scheduling, timeouts and shutdown. Botocore request validation substitutes for a live bucket in those tests. Passing tests or a local export do not prove R2 credentials, deployment or core compatibility.

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
