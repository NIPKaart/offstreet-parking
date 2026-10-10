# Delivery formats

What the collector delivers to core. Core validates both formats; see the [core delivery contract](https://github.com/NIPKaart/core/blob/main/docs/development/data-import-contract.md).

## Envelope

Both envelopes contain `format`, `dataset` and `selection` (`nl-amsterdam-garages` / `car-garages-and-pr` or `de-hamburg-pr` / `pr-all`), a new `delivery_id` UUID per retrieval, `source_count` and `records` sorted by `external_id`. The catalog adds `retrieved_at`, `complete: true` and a `source` block; observations add `fetched_at`. Timestamps are UTC ISO 8601.

## Source block

The catalog's `source` block describes the dataset so that core can discover it and an administrator can approve it once ([core ADR 0013](https://github.com/NIPKaart/core/blob/main/docs/adr/0013-discover-dataset-sources-from-deliveries-with-one-time-approval.md)). It comes from the dataset registry in `app/datasets.py` and is identical in every delivery of that dataset:

```json
"source": {
  "name": "Amsterdam parkeergarages en P+R",
  "publisher": "Gemeente Amsterdam",
  "source_url": "https://p-info.vorin-amsterdam.nl/v1/ParkingLocation.json",
  "licence": "CC-BY-4.0",
  "terms_url": "https://data.overheid.nl/dataset/9orkef6t-au29g",
  "attribution": "Gemeente Amsterdam; Actuele beschikbaarheid Parkeergarages; CC-BY 4.0.",
  "area": {"country": "NL", "subdivision": "NL-NH", "municipality": {"scheme": "nl-cbs", "code": "GM0363", "name": "Amsterdam"}},
  "bounds": [4.65, 52.2, 5.15, 52.5],
  "expected_interval_hours": 24
}
```

`licence` is an SPDX identifier, or `null` when the source publishes none. `area` uses ISO 3166 codes and the official municipality code (CBS for the Netherlands, AGS for Germany). Every facility must lie within `bounds`. Changing any of these values makes core ask for approval again, except `expected_interval_hours`.

## Catalog record

`nipkaart-offstreet-catalog-3`: what defines the facility.

```json
{
  "external_id": "06757815-834C-0E44-42B0-AE4FC4AF9CEF",
  "name": "Byzantium",
  "source_name": "P-106_ Byzantium (opendata)",
  "facility_type": "garage",
  "geometry": {"type": "Point", "coordinates": [4.88001, 52.3619]}
}
```

## Observation record

`nipkaart-offstreet-observations-2`: what the operator reports at a moment.

```json
{
  "external_id": "06757815-834C-0E44-42B0-AE4FC4AF9CEF",
  "observed_at": "2026-09-28T09:13:05Z",
  "source_state": "ok",
  "status": "counting",
  "capacity": 446,
  "available": 349
}
```

## Rules

These apply to both formats:

- `external_id` is the original source ID and joins the two streams. A missing observation never means a facility was removed.
- Capacity is an observation, not catalog metadata: it changes during the day (P4 Villa Arena went from 1046 to 1087 spaces within hours on 2026-09-28). Free spaces are only meaningful against the capacity reported with them.
- Only short-stay (visitor) values are delivered. Long-stay counts are for season-ticket holders and say nothing to visitors.
- `null` means unknown and `0` means zero. Amsterdam sends capacity `0` with `0` free for malfunctions and for P+R sites that only report open or full. A capacity of `0` is therefore unknown, and so are free spaces when the capacity is unknown.
- `status` is the operator status from the universal package: `counting` (live count), `open` or `full` (status-only sites), `closed`, `malfunction`, or `null` when unknown. A closed facility also reports `0` free, so `0` alone never means full.
- Only general spaces are delivered. General capacity or free spaces never imply accessible spaces, and accessible counts are not part of either format because sources almost never publish them.
- `name` is the package's readable name; `source_name` is the original label. Coordinates are WGS84 longitude, latitude.
- The catalog holds no live values, so a daily review only shows real metadata changes.
- Observations pass the source values on unchanged. `observed_at` is the source's own measurement time (`null` if absent), not the fetch time. `source_state` is the feed state (`ok` or `error`). Core decides freshness and must not show counts from a non-`ok` state as current availability. Sources can report more free spaces than capacity; core shows such counts without an occupancy percentage.

## Validation

A retrieval is rejected as a whole when it is empty, has duplicate or blank IDs, invalid locations or counts, more than 10,000 records or more than 32 MiB, or does not finish within 180 seconds. Amsterdam coordinates must lie within latitude 52–53 and longitude 4–6.
