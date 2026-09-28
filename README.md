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

Collect Amsterdam car garages and P+R for [NIPKaart][nipkaart] as two separate streams, delivered as JSON files to a private Cloudflare R2 bucket. Core picks them up from there. This collector has no core API or database credentials.

| Stream | Content | Cadence | R2 key | Core |
| --- | --- | --- | --- | --- |
| Catalog ([#656](https://github.com/NIPKaart/offstreet-parking/issues/656)) | Identity, name, type, location | Daily | `offstreet/<dataset>/<delivery_id>.json` | [core#1250](https://github.com/NIPKaart/core/issues/1250): review and publication |
| Observations ([#657](https://github.com/NIPKaart/offstreet-parking/issues/657)) | Source time, state, operator status, capacity, free spaces | Every 2 minutes | `offstreet-observations/<dataset>/<YYYYMMDDTHHMMSSZ>-<delivery_id>.json` | [core#1221](https://github.com/NIPKaart/core/issues/1221): live update |

Core accepts both formats (`nipkaart-offstreet-catalog-3` and `nipkaart-offstreet-observations-2`).

## Documentation

- [Delivery formats](docs/formats.md): envelopes, the source block, catalog and observation records, and validation rules.
- [Operations](docs/operations.md): scheduling, R2 delivery, retention and local export.

## Development

Use Python 3.14 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --python 3.14
uv run python -m unittest discover -s tests -v
uv run pre-commit run --all-files
```

Source HTTP and parsing live in the [`odp-amsterdam`](https://github.com/klaasnicolaas/python-odp-amsterdam) package (`>=7.1.0,<7.2.0`); this repository only selects car facilities and maps them. `main.py --fetch amsterdam|hamburg` is the legacy inspection command. It prints a count and writes nothing.

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
