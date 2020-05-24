#!/usr/bin/env bash

export LC_ALL=C.UTF-8 LANG=C.UTF-8 || export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 || {
  printf '%s\n' "WTF?!" 1>&2
  exit 1
}

help_info() {
  cat <<'EOF'
Usage: avinfo.bash [OPTIONS] [DIRECTORY]
   or: avinfo.bash [OPTIONS] [FILE]
Detect publish ID, title and date for Japanese adult videos.
Detect name and birthday for Japanese adult video stars.

OPTIONS:
    -h, --help        Show this information.
    -m, --mode        Options: dir/d, actress/a
                      dir: Only modify dir time based on its
                           content.
                      actress: Modify dir name based on actress
                               name.
    -p, --proxy       Set proxy servers. Only accessible server
                      will be used. Multiple servers are tested,
                      and the fastest will be selected.
                      Format:
                        -p 127.0.0.1:7890
                        --proxy 192.168.1.3:7890 192.168.1.5:7890
    -r, --real        Real run mode. Changes WILL be writen into disk.
    -t, --test        Test (safe) mode. Changes will only show on the
                      terminal but not written into disk.
    -n, --thread      How many threads will be run at once. The
                      default number is 3 if not specified.
                      Format:
                        -n 10

EXAMPLE:
    avinfo.bash --proxy 127.0.0.1:1080 --test -n 10 "~/Arisa Suzuki"

            Will do a recursive search for all the videos in this folder.
            Using proxy server, 10 threads, changes will not be actually applied.

    avinfo.bash --real "~/Arisa Suzuki/111815_024-carib-1080p.mp4"

            Search information for only one file, change will be
            written into disk immediately.

For better handling videos cannot be found in internat databases, it is recommend
to install exiftool. Once installed, the script will automatically try exiftool
if all other approaches fails. (sudo apt install exiftool)
EOF
}

invalid_parameter() {
  printf '%s\n' "Invalid parameter: $1" "For more information, type: 'avinfo.bash --help'"
  exit 1
}

handle_files() {
  export fifo="${TMPDIR:-/tmp}/avinfo.lock"
  mkfifo "${fifo}" && exec {fifo_fd}<>"${fifo}" && flock -n "${fifo_fd}" && trap 'rm -f -- "${fifo}"' EXIT || {
    printf '%s\n' "Unable to lock FIFO, what happened?!" 1>&2
    exit 1
  }
  printf '%s\n' '1' >&${fifo_fd}

  find "${1}" -type f -not -empty -not -path "*/[@#.]*" -printf '%Ts\0%p\0' |
    xargs -r -0 -n 12 -P "${thread}" awk -f "${script_dir}/handle_files.awk"

  exec {fifo_fd}>&-
  printf '%s\n' "${divider_bold}"
}

handle_dirs() {
  awk -v target_root="${1}" -f "${script_dir}/handle_dirs.awk" <(
    find "${1}" -depth -type 'd,f' -not -empty -not -path "*/[@#.]*" -printf '%Ts/%y\0%p\0'
  )
}

handle_actress() {
  find "${1}" -maxdepth 1 -type d -not -path "*/[@#.]*" -print0 |
    xargs -r -0 -n 1 -P "${thread}" awk -f "${script_dir}/handle_actress.awk"
}

# Begin
# Bash Version
[[ "${BASH_VERSINFO[0]}${BASH_VERSINFO[1]}" -ge 42 ]] || {
  printf '%s\n' "Error: The script requires at least bash 4.2 to run, exit." 1>&2
  exit 1
}

# Dependencies
if ! hash 'awk' 'wget' 'iconv'; then
  printf '%s\n' "Lack dependency:" "Something is missing." 1>&2
  exit 1
fi

# Awk Version
awk 'BEGIN { if (PROCINFO["version"] >= 4.2) exit 0; else exit 1 }' || {
  printf '%s\n' "Error: The script requires GNU Awk 4.2+ to run, please make sure gawk is properly installed and configed as default." 1>&2
  exit 1
}

printf -v divider_bold '%0*s' "47" ""
root_dir="$(cd "${BASH_SOURCE[0]%/*}" && pwd -P)"
script_dir="${root_dir}/scripts"
declare -xr logfile="${root_dir}/log.log" divider_bold="${divider_bold// /=}" divider_slim="${divider_bold// /-}"
printf '%s\n       %s\n                %s\n%s\n' "$divider_slim" "Adult Video Information Detector" "By David Pi" "$divider_slim"

if (($# == 0)); then
  help_info
  exit
else
  while (($#)); do
    case "$1" in
      "--help" | "-h")
        help_info
        exit
        ;;
      "--mode" | "-m")
        [[ -n $mode ]] && invalid_parameter "'--mode' or '-m' can only appear once."
        shift
        case "$1" in
          "dir" | "d") mode=dir ;;
          "actress" | "a") mode=actress ;;
          *) invalid_parameter "'--mode $1'" ;;
        esac
        ;;
      "--real" | "-r") if [[ -z $real_run ]]; then real_run=1; else invalid_parameter "'--real' or '--test' can only appear once."; fi ;;
      "--test" | "-t") if [[ -z $real_run ]]; then real_run=0; else invalid_parameter "'--real' or '--test' can only appear once."; fi ;;
      "--thread" | "-n")
        [[ -n $thread ]] && invalid_parameter "'--thread' or '-n' can only appear once."
        shift
        if [[ $1 =~ ^[0-9]+$ ]]; then
          thread="$1"
        else
          invalid_parameter "'--thread $1'"
        fi
        ;;
      "--proxy" | "-p")
        [[ -n $test_proxy ]] && invalid_parameter "'--proxy' or '-p' can only appear once."
        while (("$#")); do
          shift
          if [[ $1 =~ ^[0-9a-z\.\-]+:[0-9]+$ ]]; then
            test_proxy="$test_proxy $1"
          elif [[ $1 == "def" ]]; then
            test_proxy='127.0.0.1:7890 192.168.1.3:7890 192.168.1.5:7890'
            break
          elif [[ -z $test_proxy ]]; then
            invalid_parameter "Proxy server format: '[IP]:[PORT]'"
          else
            continue 2
          fi
        done
        ;;
      *)
        if [[ -e $1 ]]; then
          if [[ -z ${target} ]]; then
            target="${1%/}"
          else
            invalid_parameter "$1. Only one directory or file can be set."
          fi
        else
          invalid_parameter "$1"
        fi
        ;;
    esac
    shift
  done
  if [[ -z ${target} ]]; then
    printf '\033[31m%s\033[0m\n%s\n' "Lack of target!" "For more information, type: 'avinfo.bash --help'"
    exit
  fi
fi
if [[ -z ${real_run} ]]; then
  printf '%s\n' "Please select a running mode." "In Test Run (safe) mode, changes will not be written into disk." "In Real Run mode, changes will be applied immediately." "It's recommend to try a test run first." ""
  PS3='Please enter your choice: '
  select opt in "Test Run" "Real Run" "Quit"; do
    case $opt in
      "Test Run")
        real_run=0
        break
        ;;
      "Real Run")
        real_run=1
        break
        ;;
      "Quit")
        exit 0
        ;;
      *) printf '%s\n' "invalid option $REPLY" ;;
    esac
  done
fi
case "${real_run}" in
  0) printf '%s\n' "Test run mode selected, changes will NOT be written into disk." ;;
  1) printf '%s\n' "Real run mode selected, changes WILL be written into disk." ;;
esac
declare -rx real_run

if hash exiftool 1>/dev/null 2>&1; then
  declare -rx exiftool_installed=1
else
  printf '%s\n' "Lack dependency: Exiftool is not installed, will run without exif inspection."
  declare -rx exiftool_installed=0
fi

if [[ -n $test_proxy ]]; then
  printf '%s' 'Testing proxies... ' 1>&2
  IFS= read -r i < <(
    for i in ${test_proxy}; do
      wget -e https_proxy="http://${i}" -qO '/dev/null' --timeout=10 --spider 'https://www.google.com' 1>/dev/null 2>&1 && printf '%s\n' "${i}" &
    done
  )
  if [[ -n ${i} ]]; then
    export http_proxy="http://${i}" https_proxy="http://${i}"
    printf '%s\n' "Using proxy: ${i}." 1>&2
  else
    printf '%s\n' 'No proxy is available.' 1>&2
  fi
fi

# Filesystem Maximum Filename Length
max_length="$(stat -f -c '%l' "${target}")"
[[ ${max_length} =~ ^[0-9]+$ ]] || max_length=255
declare -rx max_length

printf '%s\n' "${divider_bold}"

if [[ -d ${target} ]]; then
  printf '%s\n' "Task start using ${thread:=3} threads."
  case "${mode}" in
    "dir")
      handle_dirs "${target}"
      ;;
    "actress")
      handle_actress "${target}"
      ;;
    *)
      handle_files "${target}"
      handle_dirs "${target}"
      ;;
  esac
else
  case "${mode}" in
    "dir" | "actress")
      printf '%s\n' "Error: Cannot select mode '${mode}' when target is a regular file." >&2
      exit 1
      ;;
    *)
      awk -f "${script_dir}/handle_files.awk" "$(date -r "${target}" '+%s')" "${target}"
      ;;
  esac

fi

exit 0
