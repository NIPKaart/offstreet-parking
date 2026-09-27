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

Prepare offstreet source collection for [NIPKaart][nipkaart]. Existing source clients can be inspected locally; catalog mapping and delivery follow in #656.

## Existing source clients

| Country | City | Type |
| --- | --- | --- |
| Netherlands | [Amsterdam](https://github.com/klaasnicolaas/python-garages-amsterdam) | Parking garages |
| Germany | [Hamburg](https://github.com/klaasnicolaas/python-hamburg) | Park and rides |

## Development

Use Python 3.14 and [uv](https://docs.astral.sh/uv/), matching the municipal collector tooling. `uv.lock` replaces `poetry.lock`, preserving the versions and ranges of retained dependencies. The unused PyMySQL and python-dotenv dependencies are removed. CI and Docker enforce the lockfile.

```bash
uv sync --locked --python 3.14
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
| Entrypoint | `main.py` defaults to help and provides a finite `--fetch` command. The old continuous writer and polling schedule are removed. |
| Universal source packages | Locked `odp-amsterdam` 6.1.2 and `hamburg` 3.0.1 own HTTP access, parsing and source models. Source parsing and parser fixtures belong upstream. |
| NIPKaart wrappers | `app/cities/netherlands/amsterdam.py` and `app/cities/germany/hamburg.py` retain their existing package calls. Hamburg requests at most 40 park-and-rides; completeness is unverified. Source objects are returned without legacy database mapping. |
| Removed database coupling | Both `upload_data` methods previously upserted into MySQL `parking_offstreet`; importing `app.database` opened a connection. Those methods, the connection/delete helpers, coordinate-derived IDs, country/province database IDs and unknown-to-zero mapping are removed. |
| Runtime and dependencies | Python 3.14 is the baseline for local development, CI and Docker; retained package versions are unchanged. Standard project metadata, uv, default `cities`/`dev` groups and locked installation follow disabled-parking#779. Docker includes `uv.lock`, pins uv and uses Bookworm instead of Buster. `.env` and local virtual environments are excluded. |
| Deployment definitions | The old Compose/Swarm definitions and credential template are removed. Docker now defaults to offline help. This revision does not update or stop any running deployment. |

This follows [disabled-parking#779](https://github.com/NIPKaart/disabled-parking/pull/779) for tooling and [#780](https://github.com/NIPKaart/disabled-parking/pull/780) for removing the SQL runtime while preserving reusable source clients. NIPKaart source selection, mapping and future transport remain here. No shared framework is introduced.

Catalog source verification, stable source IDs, capacity semantics, mapping examples, the bounded JSON delivery and private R2 transfer belong to #656 with NIPKaart/core#1250. No adapter, second transport format, core intake or live occupancy (#657) is implemented here. General free capacity does not establish accessible-space availability.

## Container smoke check

```bash
docker build -t nipkaart-offstreet .
docker run --rm --network none nipkaart-offstreet
# Optional live source inspection:
docker run --rm nipkaart-offstreet main.py --fetch amsterdam
```

The image is a source-inspection tool, not yet a scheduled producer. Do not replace existing production jobs with this revision: keep their existing image/revision until an explicit cutover is agreed. The previous SQL code and deployment definitions remain available in Git history; no legacy mode is carried in the new collector code, and no existing production process or data is modified by this preparation.

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
