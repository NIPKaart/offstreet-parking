# Sources

Source HTTP and parsing belong to the universal packages; the collector maps their records to the [delivery formats](formats.md). Source packages are pinned exactly in `pyproject.toml` and `uv.lock`: `odp-amsterdam==7.2.0`, `hamburg==4.0.0` and `odp-gent==1.0.0`. Update those pins deliberately and validate both streams before delivery.

| City | Dataset / selection | Package retrieval |
| --- | --- | --- |
| Amsterdam | `nl-amsterdam-garages` / `car-garages-and-pr` | `odp-amsterdam.all_garages(vehicle="car")`: complete feed without pagination. |
| Hamburg | `de-hamburg-pr` / `pr-all` | `hamburg.park_and_ride_collection()`: count/ID-verified pagination. |
| Gent | `be-gent-parking` / `live-facilities-all` | `odp_gent.parking_collection()`: count/ID-verified pagination of the unified live feed. |

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


## Gent

Checked on **2026-10-13**. The [official live dataset](https://data.stad.gent/explore/dataset/bezetting-parkeergarages-real-time/information/) and [metadata API](https://data.stad.gent/api/explore/v2.1/catalog/datasets/bezetting-parkeergarages-real-time) identify Mobiliteitsbedrijf Gent as publisher and permit [Modellicentie Gratis Hergebruik](https://www.vlaanderen.be/digitaal-vlaanderen/onze-diensten-en-platformen/open-data/voorwaarden-voor-het-hergebruik-van-overheidsinformatie/modellicentie-gratis-hergebruik). Attribution names the publisher, dataset, licence and NIPKaart normalization. `source.licence` is null because the named model licence has no verified identifier compatible with core's licence-code field; the full terms URL and original licence name remain in attribution. This is established reuse evidence, not a claim that the data has no licence.

The full [source response](https://data.stad.gent/api/records/1.0/search/?dataset=bezetting-parkeergarages-real-time&rows=100&sort=id) reported 14 records. Pagination uses `nhits`, ordered original IDs, page lengths and unique-ID checks; exceeding the safety ceiling fails instead of silently truncating. Both streams map all 14: 10 garages, 2 P+R and 2 parking lots. This is complete coverage of this feed, not of all parking in Gent: the separate [locations dataset](https://data.stad.gent/explore/dataset/locaties-openbare-parkings-gent/information/) contained 36 records. The former `real-time-bezetting-pr-gent` endpoint returned 404 and is not used.

Identity is the original `fields.id` facility URL, not the changing portal `recordid`, name or coordinate. Two repeated complete reads retained all 14 original IDs while all measurement times advanced. This establishes observed continuity, not an operator guarantee against future ID changes. Catalog and observations use the same original facility IDs and selection; no live refresh creates, removes or publishes a facility. Gent uses `be-ins` / `44021` (also present in source metadata `be_80_44021`), province `BE-VOV`; core already supports this code scheme.

### Facility types

The feed's `offStreetParkingGround` label is not reliable enough to equate every row with a surface parking lot. Reviewed original-ID overrides preserve these distinctions:

| Facility | Delivered type | Evidence |
| --- | --- | --- |
| Dok noord | `garage` | Official feed description: underground garage; [municipal operator reference](https://stad.gent/en/opening-hours-addresses/parking-dok-noord). |
| Tolhuis | `garage` | [Gent municipal page](https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/parkings-gent/parking-tolhuis): underground public parking, Tolhuislaan 77–79 / entrance Berouw 55. This is not the Tolhuis parking in Antwerp. |
| Getouw | `garage` | [Municipal facilities table](https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/parkings-gent/parking-het-getouw): above-ground garage. |
| Ledeberg | `park_and_ride` | [Municipal page](https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/parkings-gent/parking-ledeberg): garage with explicitly described P+R use. |
| P+R The Loop | `park_and_ride` | [Municipal P+R description](https://stad.gent/nl/mobiliteit-openbare-werken/parkeren/park-and-ride-pr/pr-loop). |
| The Loop | `parking_lot` | [Municipal page](https://stad.gent/nl/loop/mobiliteit-loop): public parking grounds B/C; a separate source ID from P+R The Loop. |
| B-Park Dampoort | `parking_lot` | [NMBS public parking](https://www.belgiantrain.be/nl/station-information/car-or-bike-at-station/b-parking/my-b-parking/gent-dampoort); source type `offStreetParkingGround`. |

Other source `carPark` rows map to `garage`; other `offStreetParkingGround` rows map to `parking_lot`. Unknown source types fail the delivery. Overrides select facility type only and never replace the original identity or name.

### Observations and limits

`lastupdate` is the original timezone-aware measurement time, converted to UTC. Portal processing and fetch times do not replace it. The metadata advertises updates every three minutes; repeated reads on this date showed advances of 1–74 seconds in individual source times, with reading ages around four minutes. The two-minute poll reuses the existing cadence and does not promise that each facility updates on each poll. Core's ten-minute freshness threshold remains unchanged.

`totalcapacity` is theoretical general capacity and explicitly includes reserved/accessibility spaces; `availablecapacity` is the reported general free count. Neither proves accessible availability. `temporaryclosed=true` or `isopennow=false` maps to `closed` without rewriting counts. Otherwise known counts map to `counting`, or an explicit open flag to `open`. Unknown counts remain null; zero remains zero. `source_state=ok` means a successfully retrieved and decoded source record, not verified sensor health; the source has no separate sensor-health guarantee. Failed retrieval delivers nothing. Missing/invalid/undated source times stay unknown, and core does not replace newer dated measurements with them.

The collector pins the published [odp-gent v1.0.0](https://github.com/klaasnicolaas/python-odp-gent/releases/tag/v1.0.0) in both dependency files; no Git dependency is required. Deploy the compatible core `parking_lot` consumer/migration first. Real local exports and the isolated core acceptance test are evidence of contract behavior; live R2 uptake, administrator approval/publication in the target environment and production activation under core#1303 remain separate gates.
