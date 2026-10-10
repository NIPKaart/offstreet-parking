# Sources

Source HTTP and parsing belong to the universal packages; the collector maps their records to the [delivery formats](formats.md). Source packages are pinned exactly in `pyproject.toml` and `uv.lock`: `odp-amsterdam==7.2.0` and `hamburg==4.0.0`. Update those pins deliberately and validate both streams before delivery.

| City | Dataset / selection | Package retrieval |
| --- | --- | --- |
| Amsterdam | `nl-amsterdam-garages` / `car-garages-and-pr` | `odp-amsterdam.all_garages(vehicle="car")`: complete feed without pagination. |
| Hamburg | `de-hamburg-pr` / `pr-all` | `hamburg.park_and_ride_collection()`: count/ID-verified pagination. |

## Amsterdam

The selection includes car garages and P+R, with general short-stay counts only. Long-stay counts are excluded. Capacity `0` can be a source placeholder for unknown capacity; see the [format rules](formats.md#rules).

## Hamburg

The [official source](https://api.hamburg.de/datasets/v1/p_und_r) and [reuse terms](https://suche.transparenz.hamburg.de/dataset/park-ride-anlagen-hamburg32) were checked on 2026-10-10: 38 facilities, original numeric IDs, WGS84 points, DL-DE-BY-2.0 with attribution to Freie und Hansestadt Hamburg/BVM. The municipality is `de-ags` / `02000000`, region `DE-HH`; core must support that code scheme before approval.

The catalog represents the published P+R selection, not all Hamburg garages. The former garage endpoint is unavailable and is not substituted into this selection. Catalogs and observations retain the same original feature IDs.

Hamburg supplies nullable general capacity/free counts and local Berlin measurement times. Missing, ambiguous DST or invalid source times stay unknown; older readings remain old when fetched again. Counts do not imply accessible-space availability. There is no verified source-wide revision or guarantee that every reading updates each cycle. The two-minute observation poll is an operator default, not a guarantee about each site's measurement cadence.

## Follow-up sources

Gent, Brussel, Liège and Münster remain follow-up work in [#679](https://github.com/NIPKaart/offstreet-parking/issues/679).
