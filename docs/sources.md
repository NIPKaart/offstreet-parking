# Sources

Source HTTP and parsing belong to the universal packages; the collector maps their records to the [delivery formats](formats.md). Source packages are pinned exactly in `pyproject.toml` and `uv.lock`: `odp-amsterdam==7.2.0` and `hamburg==4.0.0`. Update those pins deliberately and validate both streams before delivery.

| City | Dataset / selection | Package retrieval |
| --- | --- | --- |
| Amsterdam | `nl-amsterdam-garages` / `car-garages-and-pr` | `odp-amsterdam.all_garages(vehicle="car")`: complete feed without pagination. |
| Hamburg | `de-hamburg-pr` / `pr-all` | `hamburg.park_and_ride_collection()`: count/ID-verified pagination. |

## Amsterdam

The selection includes car garages and P+R, with general short-stay counts only. Long-stay counts are excluded. Capacity `0` can be a source placeholder for unknown capacity; see the [format rules](formats.md#rules).

## Hamburg

The [official source](https://api.hamburg.de/datasets/v1/p_und_r) and [reuse terms](https://suche.transparenz.hamburg.de/dataset/park-ride-anlagen-hamburg32) were checked on 2026-10-10: 38 facilities, WGS84 points, DL-DE-BY-2.0 with attribution to Freie und Hansestadt Hamburg/BVM. The municipality is `de-ags` / `02000000`, region `DE-HH`; core must support that code scheme before approval.

The catalog represents the published P+R selection, not all Hamburg garages. The former garage endpoint is unavailable and is not substituted into this selection. The numeric `gid`/feature ID changes when the source refreshes and must not be persisted as facility identity. Both streams preserve the original numeric source ID. Core resolves facility identity across versions; observations additionally carry same-fetch location claims so they can be matched without a catalog review for every refresh.

Hamburg supplies nullable general capacity/free counts and local Berlin measurement times. Missing, ambiguous DST or invalid source times stay unknown; older readings remain old when fetched again. Counts do not imply accessible-space availability. There is no verified source-wide revision or guarantee that every reading updates each cycle. The [official metadata](https://metaver.de/trefferanzeige?docuuid=60D2A087-811B-4D55-9179-5F916DC5287F) describes a five-minute update cycle. The two-minute observation poll is an operator default, not a guarantee about each site's measurement cadence. Core retains its ten-minute freshness threshold on the original observation time; old or undated counts are never made current by fetching again.

### Identity reconciliation in core

Hamburg catalogs retain original source IDs and use the existing catalog contract. Observations use `nipkaart-offstreet-observations-3` with `identity_records`: catalog-format name, source name, facility type and point claims obtained from the same `park_and_ride_collection()` call as the occupancy records. The same ID set must occur in both lists. No second fetch is used to infer an association between independently refreshed IDs.

Core owns fixed facility IDs, matching, ambiguity review and publication. The collector never decides that nearby records are the same physical facility and never invents UUIDs for them. New or uncertain records remain catalog-review work; live observations cannot create or publish facilities. See the authoritative [core integration contract](https://github.com/NIPKaart/core/blob/main/docs/development/integration-contracts.md) for consumer matching policy.

Existing pending bytes remain immutable and are retried unchanged. Deploy the compatible core consumer before the version-3 producer; production activation remains core#1303.
