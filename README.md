# Rina: The All-in-One AV Toolbox

Rina is a command-line tool for managing AV content. It searches through a wide range of online databases and helps to organize local files.

## Features

### Video Scraping
- **Command**: `rina video <directory>`
- Extracts JAV IDs from local files and scrapes data from online databases.
- Renames video files based on ID and title. Updates file timestamps to match the release dates.
- Offers flexible and customizable scanning options.

### Idol Identity Search
- **Command**: `rina idol <your favorite idol>`
- Cross-searches for names, aliases, and ages of JAV idols, aiming to identify their most recognized identities.
- Renames local folders to reflect the idol's name and birth year.

### Idol Search by Birth Year
- **Command**: `rina birth <year>`
- Searches for idols born within a specified year range and active in a recent timespan.
- Filters results based on recent activity, with an option for solo performances only.

### Western Video Scraping
- **Command**: `rina western <directory>`
- Renames files based on site, date, performers, and title. Updates file timestamps to match release dates.
- Requires at least one API key. See [Configuration](#configuration).

### Video Concatenation
- **Command**: `rina concat <directory>`
- Identifies and losslessly concatenates consecutive videos into a single file.

### Directory Timestamp Update
- **Command**: `rina touch <directory>`
- Updates directory timestamps to match the most recent file they contain.

## Installation

To get started, you'll need Python 3.10+. Then clone the GitHub repository and install the package:

```bash
git clone https://github.com/libertypi/rina.git
cd rina
pip install .
```

After installation, `rina` will be accessible from the command line.

## Configuration

Rina stores configurations in `rina/profile/config.json`. Use the `rina set` command to manage them.

```bash
# List the current configuration
rina set

# Set a single field
rina set tpdb_api YOUR_KEY

# Prompt interactively
rina set nordvpn
```

The supported fields:

| Field | Used by | Required for |
|---|---|---|
| `tpdb_api` | `western` | Western scraping |
| `stashdb_api` | `western` | Western scraping |
| `nordvpn_user`, `nordvpn_pass` | `-p ...` | for bypassing geo block and the `-p` flag |

## Usage

Run `rina -h` for available commands.

Run `rina <command> -h` for detailed help on each command.

## Local File Structure

Rina works best with the following file structure. Each folder is named after an idol, containing their contents.

```
.
├── <idol name 1>
│   ├── video 1.wmv
│   └── video 2.mp4
├── <idol name 2>
│   ├── video 1.mkv
│   ├── video 2.avi
│   └── video 3.mpeg
...
```
