# spro2tod

Extract Time of Day (ToD) data from Vola SPRO timing files.

SPRO files are used in ski racing to record timing data. This tool extracts all Start and Finish times for all bibs across all runs and outputs them as CSV.

## Usage

### Interactive mode

Just run the program and it will prompt for input:

```
$ spro2tod
SPRO file: race.spro
Output CSV file [race-tod.csv]:
Reading /path/to/race.spro
Extracting ToD
Extracted times for 29 bibs and 2 runs
Writing to /current/dir/race-tod.csv
```

### Command line

```bash
# Use default output filename (<input>-tod.csv)
spro2tod race.spro

# Specify output filename
spro2tod race.spro results.csv
```

## Output format

CSV with columns: Bib, Run, Channel, ToD

```csv
Bib,Run,Channel,ToD
613,1,Start,10h17:07.3180
613,1,Finish,10h17:45.4274
613,2,Start,10h32:25.7294
613,2,Finish,10h33:01.9466
7736,2,Start,10h31:04.6198
7736,2,Finish,DNF
```

A Finish entry with `DNF` as the ToD indicates a Did Not Finish or Disqualification.

## Installation

### Download pre-built executable

Download the appropriate executable for your platform from the [Releases](https://github.com/dansherpa/spro2tod/releases) page:

- `spro2tod-linux-x64` - Linux
- `spro2tod-macos-apple-silicon` - macOS (M1/M2/M3/M4)
- `spro2tod-windows-x64.exe` - Windows

### Install with pip (macOS Intel and others)

If you have Python 3.8+ installed, you can install directly with pip:

```bash
pip install git+https://github.com/dansherpa/spro2tod.git
```

Then run with:

```bash
spro2tod
```

To check if you have Python installed:

```bash
python3 --version
```

If not installed, download from https://www.python.org/downloads/

## Building a release

Releases are built automatically by GitHub Actions when you create a new release.

1. Go to [Releases](https://github.com/dansherpa/spro2tod/releases)
2. Click "Draft a new release"
3. Click "Choose a tag" and create a new tag (e.g., `v0.1.0`)
4. Enter a release title and description
5. Click "Publish release"

The workflow will automatically build executables for all platforms and attach them to the release. This typically completes within a few minutes.

## License

MIT
