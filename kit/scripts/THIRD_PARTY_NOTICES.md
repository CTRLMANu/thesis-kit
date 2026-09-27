# Third-party notices

## sources.py

`sources.py` is derived from `scripts/sources.py` in the `autonomous-research` skill (published there as `opendraft`) of [getedgehq/skills](https://github.com/getedgehq/skills), commit `34df0477`, Copyright 2026 Floom, licensed under the Apache License, Version 2.0. The full license text is in [`LICENSE-APACHE-2.0`](LICENSE-APACHE-2.0) in this folder.

Modified for thesis-kit in 2026: renamed the user agent and the contact variable; `verify` also returns authors, year, venue, volume, pages, abstract and editorial notices (retractions, corrections); added the `check` and `details` commands, an OpenAlex title search, and a polite retry when a service rate-limits. The modified file remains under the Apache License 2.0.

The getedgehq script is itself ported from OpenDraft (https://github.com/federicodeponte/opendraft), which is licensed under the MIT License:

> MIT License
>
> Copyright (c) 2025 SCAILE Technologies GmbH
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Everything else

`bibliography.py` and every other file in this repository are thesis-kit's own work under the MIT License in [`LICENSE`](../../LICENSE) at the repository root. The exposé workflow (`kit/workflows/make-expose.md`) follows the order of OpenDraft's research stages but is written from scratch.

## Services used at run time

The scripts ask the public APIs of Crossref, DataCite, OpenAlex and doi.org, and download citation style files from the Zotero Style Repository (https://www.zotero.org/styles, CSL styles under CC BY-SA 3.0) into `~/.thesis-kit/styles/` on the student's computer. None of that data is shipped with this repository.
