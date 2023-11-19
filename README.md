# Rina: All-in-One JAV Toolbox

Rina is a command-line tool for managing Japanese AV content. It searches through a wide range of online databases and processes local files.

## Features

### Video Scraping
- **Command**: `video`
- Extracts JAV IDs from local files and scrapes data from online databases.
- Renames video files based on ID and title. Updates file timestamps to match the release dates.
- Offers flexible and customizable scanning options.
- **Try**: `rina video <directory>`

### Idol Identity Search
- **Command**: `idol`
- Cross-searches for names, aliases, and ages of JAV idols, aiming to identify their most recognized identities.
- Renames local folders to reflect the idol's name and birth year.
- Try: `rina idol <your favorite idol>`

### Idol Search by Birth Year
- **Command**: `birth`
- Searches for idols born within a specified year range and active in a recent timespan.
- Filters results based on recent activity and content types, including uncensored and solo performances.
- Try: `rina birth 1993-1995`

### Video Concatenation
- **Command**: `concat`
- Identifies and losslessly concatenates consecutive videos into a single file.

### Directory Timestamp Update
- **Command**: `dir`
- Updates directory timestamps to match the most recent file they contain.

## Installation

To get started, you'll need Python 3. Then clone the GitHub repository and install the package:

```bash
git clone https://github.com/libertypi/rina.git
cd rina
pip install .
```

After installation, `rina` will be accessible from the command line.

## Usage

Run `rina -h` for available commands.

Run `rina <command> -h` for detailed help on each command.

## Local File Structure

Rina works best with the following file structure. Each folder is named after an idol, containing their contents.

```
.
├── <idol name>
│   ├── video 1.wmv
│   └── video 2.mp4
├── <idol name>
│   ├── video 1.mkv
│   ├── video 2.avi
│   └── video 3.mpeg
...
```
