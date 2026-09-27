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

This project makes it possible to collect data from municipalities about off-street parking spaces (garages or park and rides) and upload them to the [NIPKaart][nipkaart] platform.

## Supported cities

| Country | City | Type | Update interval |
|:--------|:-----|:-----|:----------------|
| Netherlands | [Amsterdam](https://github.com/klaasnicolaas/python-garages-amsterdam) | Parking garages | Every 10 minutes |
| Germany | [Hamburg](https://github.com/klaasnicolaas/python-hamburg) | Park and rides | Every 30 minutes (paused in midnight) |

## Development

Use Python 3.11 and [uv](https://docs.astral.sh/uv/), matching the municipal collector tooling. Python 3.11 remains supported by the existing source packages; there is no compatibility reason to raise that minimum here. `uv.lock` replaces `poetry.lock`, preserving its package versions and dependency ranges. CI and Docker enforce the lockfile.

```bash
uv sync --locked --python 3.11
uv lock --check
uv run python main.py --help
uv run python -m unittest discover -s tests -v
uv run pre-commit run --all-files
```

No `.env`, core API credentials or database credentials are needed for installation, help or offline tests. Running `main.py` without arguments prints help and exits. Install local Git hooks with `uv run pre-commit install` if desired. CI runs the same offline tests, lockfile check, Ruff, Pylint, YAML and file checks.

To inspect an existing source once (outbound provider access required):

```bash
uv run python main.py --fetch amsterdam
uv run python main.py --fetch hamburg
```

These commands print only a record count and exit, without loading `.env`, connecting to MySQL, writing files or uploading data. Provider failures exit unsuccessfully. They are source smoke checks, not a catalog export or evidence that a source is complete or suitable for publication. Offline tests replace package clients and never contact live providers.

## Repository inventory and collector boundary

| Area | Retained behavior and limitations |
| --- | --- |
| Entrypoint | `main.py` provides safe help and a finite `--fetch` command; `--legacy` explicitly selects the existing continuous writer. |
| Universal source packages | Locked `odp-amsterdam` 6.1.2 and `hamburg` 3.0.1 own HTTP access, parsing and source models. Source parsing and parser fixtures belong upstream. |
| NIPKaart wrappers | `app/cities/netherlands/amsterdam.py` and `app/cities/germany/hamburg.py` select package calls and hold legacy NIPKaart mapping. Hamburg currently requests at most 40 park-and-rides; completeness is unverified. |
| Legacy identity and mapping | `City` holds old country/province IDs. `get_unique_number` derives an ID from coordinates; Amsterdam converts unknown counts to zero. Neither behavior is a future catalog contract. |
| Direct database writes | Both `upload_data` methods upsert into the old MySQL `parking_offstreet` table. Importing `app.database` opens a connection; only explicit legacy writes load it. The module also contains a delete helper and a connection diagnostic, unused by the command. |
| Runtime and dependencies | Python 3.11 and existing package versions are retained. Standard project metadata, `uv`, default `cities`/`dev` groups and locked installation follow disabled-parking#779, replacing deprecated Poetry metadata and a separate toolchain. Docker includes `uv.lock`, pins uv and uses Debian Bookworm instead of the obsolete Buster base. `.env` and local virtual environments are excluded from the image. |
| Existing deployment | Docker still defaults to `main.py --legacy`; `docker-compose.yml` and `deploy/*.yml` remain legacy deployment definitions. No running jobs or data are changed by this preparation. |

The reusable boundary is the universal source clients and their returned objects. NIPKaart source selection, mapping and future transport remain in this repository, following the municipal collector's finite-command and offline-test approach without introducing a shared framework. The old MySQL schema, coordinate-derived IDs, unknown-to-zero mapping and polling loop must not become the new collector contract. Existing SQL behavior is retained, including its limitations, rather than migrated to core's PostgreSQL schema.

Catalog source verification, stable source IDs, capacity semantics, mapping examples, the bounded JSON delivery and private R2 transfer belong to #656 with NIPKaart/core#1250. No adapter, second transport format, core intake or live occupancy (#657) is implemented here. General free capacity does not establish accessible-space availability.

## Legacy operation

Only legacy operation needs the variables in `.env.example`. Set `CITY` to `amsterdam` or `hamburg`, `WAIT_TIME` to a positive number of minutes and supply the old MySQL credentials. Settings are loaded after command parsing and before validation.

```bash
uv run python main.py --legacy
```

Existing shell jobs that invoke `python main.py` directly must explicitly add `--legacy` when adopting this revision. Container defaults preserve the writer, but credentials must now be supplied at runtime rather than baked into the image. Do not deploy or stop existing jobs as part of repository preparation.

```bash
docker build -t nipkaart-offstreet .
# Safe offline check; overrides the image's legacy command:
docker run --rm nipkaart-offstreet main.py --help
# Explicit legacy operation against the old database:
docker run --env-file .env --name nipkaart-offstreet nipkaart-offstreet
```

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
