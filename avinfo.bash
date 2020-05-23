#!/usr/bin/env bash

export LC_ALL=C.UTF-8 LANG=C.UTF-8 || export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 || {
  printf '%s\n' "WTF?!"
  exit 1
}

handle_dirs() {
  awk -v target_root="${1}" -f "${script_dir}/handle_dirs.awk" <(
    find "${1}" -depth -type 'd,f' -not -empty -not -path "*/[@#.]*" -printf '%Ts/%y\0%p\0'
  )
}

handle_actress() {

  rename_actress_dir() {
    name="$(sed -En 's/[[:space:] ]|\([^\)]*\)|【.*】|（.*）//g;1p' <<<"$result")"
    birth="$(sed -n '2p' <<<"$result")"
    new_name="${name}(${birth})"
    new_dir="${target_dir%/*}/${new_name}"
    if [[ ${target_dir} != "${new_dir}" ]]; then
      color_start='\033[93m'
      color_end='\033[0m'
      if ((real_run)); then
        if mv "${target_dir}" "${new_dir}"; then
          {
            flock -x "${fd}"
            printf '[%(%F %T)T] Rename Dir:\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n' "-1" \
              "Original path" "${target_dir}" \
              "New name" "${new_name}" \
              "Source" "${source}" \
              "${divider_slim}" >&${fd}
          } {fd}>>"${logfile}"
          exec {fd}>&-
        fi
      fi
    fi
    printf "${color_start}%s ===> %s <=== %s${color_end}\n" "${actress_name}" "${new_name}" "${source}"
    exit 0
  }

  target_dir="${1}"
  actress_name="${target_dir##*/}"
  actress_name="${actress_name%([0-9][0-9][0-9][0-9]*}"
  [[ $actress_name == "$target_dir" || $actress_name =~ ^[A-Za-z0-9[:space:][:punct:]]*$ ]] && return

  # ja.wikipedia.org
  result="$(
    wget -qO- "https://ja.wikipedia.org/wiki/${actress_name}" |
      awk '
      ! name && /<h1 id="firstHeading" class="firstHeading"[^>]*>[^<]+<\/h1>/ {
        name = $0
        gsub(/^.*<h1 id="firstHeading" class="firstHeading"[^>]*>[[:space:]]*|[[:space:]]*<\/h1>.*$/, "", name)
      }

      /生年月日/ {
        do {
          if (! birth && match($0, /title="([0-9]{4})年">[0-9]{4}年<\/a><a href="[^"]+" title="([0-9]{1,2})月([0-9]{1,2})日">[0-9]{1,2}月[0-9]{1,2}日<\/a>/, a)) {
            y = a[1]
            m = sprintf("%02d", a[2])
            d = sprintf("%02d", a[3])
            birth = (y "-" m "-" d)
          }
          if ($0 ~ /title="AV女優">AV女優<\/a>/) {
            flag = 1
          }
          if (flag && birth) {
            print name
            print birth
            exit
          }
        } while ((getline) > 0)
      }'
  )"
  if [[ -n $result ]]; then
    source='ja.wikipedia.org'
    rename_actress_dir
  fi

  # seesaawiki.jp
  result="$(wget -qO- "https://seesaawiki.jp/av_neme/search?keywords=$(iconv -c -f UTF-8 -t EUC-JP <<<"${actress_name}")" | iconv -c -f EUC-JP -t UTF-8 |
    awk -v actress_name="${actress_name}" '
        /<div class="body">/,/<\/div><!-- \/body -->/ {
            if ( match($0, /<h3 class="keyword"><a href="[^"]+">[^<]+<\/a><\/h3>/) )
            {
                name = substr($0, RSTART, RLENGTH)
                gsub(/^<h3 class="keyword"><a href="[^"]+">[[:space:]]*|[[:space:]]*<\/a><\/h3>$/, "", name)
                if ( name == actress_name ) flag = 1
                next
            }
            if ( !flag && name && $0 ~ actress_name ) flag = 1
            if ( flag && match($0, /生年月日.*[0-9]{4}年[[:space:]0-9]+月[[:space:]0-9]+日/ ) )
            {
                birth = substr($0, RSTART, RLENGTH)
                gsub(/^[^0-9]+|[[:space:]]+$/, "", birth)
                y = gensub(/([0-9]{4})年.*/, "\\1", 1, birth)
                m = sprintf("%02d", gensub(/.*[^0-9]([0-9]+)月.*/, "\\1", 1, birth))
                d = sprintf("%02d", gensub(/.*[^0-9]([0-9]+)日.*/, "\\1", 1, birth))
                birth = ( y "-" m "-" d )
        print name ; print birth
                exit
            }
        }
        /<\/div><!-- \/body -->/ { name = ""; birth = ""; flag = "" }
       ')"
  if [[ -n $result ]]; then
    source='seesaawiki.jp'
    rename_actress_dir
  fi

  # minnano-av.com
  minnano_av() {
    awk -v actress_name="${actress_name}" '
      /<h1>[^<]+<span>.*<\/span><\/h1>/ {
        gsub(/<span>[^<]*<\/span>/,"",$0)
        gsub(/^.*<h1>[[:space:]]*|[[:space:]]*<\/h1>.*$/, "", $0)
        name = $0
      }
      name && match($0, /生年月日.*[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日/) {
        date = substr($0, RSTART, RLENGTH)
        y = gensub(/.*([0-9]{4})年.*/, "\\1", 1, date)
        m = sprintf("%02d", gensub(/.*[^0-9]([0-9]{1,2})月.*/, "\\1", 1, date) )
        d = sprintf("%02d", gensub(/.*[^0-9]([0-9]{1,2})日/, "\\1", 1, date) )
        if ( y && m && d )
        {
          birth = ( y "-" m "-" d )
          print name ; print birth
          exit
        }
      }'
  }
  search="$(wget -qO- "http://www.minnano-av.com/search_result.php?search_scope=actress&search_word=${actress_name}")"
  if [[ $search == *'AV女優の検索結果'* ]]; then
    url="$(
      awk -v actress_name="${actress_name}" -v url='http://www.minnano-av.com' '
        /<table[^>]*class="tbllist actress">/,/<\/table>/{
            if ( $0 ~ "<h2[^>]*><a href=[^>]*>"actress_name"[^<]*<\\/a><\\/h2>" )
            {
                gsub(/^.*<h2[^>]*><a href="|(\?|").*$/, "", $0)
                print ( url"/"$0 )
            }
        }' <<<"$search"
    )"
    for i in $url; do
      result="$(wget -qO- "${i}" | minnano_av)"
      [[ -n $result ]] && break
    done
  else
    result="$(minnano_av <<<"$search")"
  fi
  if [[ -n $result ]]; then
    source='minnano-av.com'
    rename_actress_dir
  fi

  # mankowomiseruavzyoyu.blog.fc2.com
  result="$(
    wget -qO- "http://mankowomiseruavzyoyu.blog.fc2.com/?q=${actress_name}" |
      awk -v actress_name="${actress_name}" '
      /dc:description="[^"]+"/ {
          gsub(/^[[:space:]]*dc:description="|"[[:space:]]*$|&[^;]*;/, " ", $0)
          name = $1
          gsub(/[[:space:] ]/,"",name)
          for (i=2; i<=NF; i++)
          {
              if ( $i ~ "生年月日" && $(i+1) ~ /[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日/ ) birth = $(i+1)
              else if ( $i ~ "別名" ) alias = $(i+1)
              if (birth && alias) break
          }
          y = gensub(/([0-9]{4})年.*/, "\\1", 1, birth)
          m = sprintf("%02d", gensub(/.*[^0-9]([0-9]+)月.*/, "\\1", 1, birth))
          d = sprintf("%02d", gensub(/.*[^0-9]([0-9]+)日/, "\\1", 1, birth))
          if ( y && m && d ) birth = ( y "-" m "-" d )
          if ( name && birth && ( name ~ actress_name || alias ~ actress_name ) )
          {
              print name ; print birth
              exit
          }
          else { name=""; birth=""; alias="" }
      }
    '
  )"
  if [[ -n $result ]]; then
    source='mankowomiseruavzyoyu.blog.fc2.com'
    rename_actress_dir
  else
    printf "\033[31m%s ===> Failed.\033[0m\n" "${actress_name}"
  fi
}

help_info() {
  cat <<'EOF'
Usage: avinfo.sh [OPTIONS] [DIRECTORY]
   or: avinfo.sh [OPTIONS] [FILE]
Detect publish ID, title and date for Japanese adult videos.

OPTIONS:
    -h, --help        Show this information.
    -m, --mode        Options: dir/d, actress/a
                      dir: Only modify dir time based on its
                           content.
                      actress: Modify dir name based on actress
                               name.
    -p, --proxy       Set proxy servers. Only accessible server
                      will be used. Multiple servers are allowed,
                      but only one of which will be used.
                      Format:
                        -p 127.0.0.1:7890
                        --proxy 192.168.1.3:7890 192.168.1.5:7890
    -r, --real        Real run mode. Changes WILL be writen into disk.
    -t, --test        Test (safe) mode. Changes will only show on the
                      screen but not written into disk.
    -n, --thread      How many threads will be run at once. The
                      default number is 3 if not specified.
                      Format:
                        -n 10

EXAMPLE:
    avinfo.sh --proxy 127.0.0.1:1080 --test -n 10 "~/Arisa Suzuki"

            Will do a recursive search for all the videos in the folder.
            Using proxy server, 10 threads, changes will not be actually applied.

    avinfo.sh --real "~/Arisa Suzuki/111815_024-carib-1080p.mp4"

            Search information for only one file, change will be
            written into disk immediately.

For better handling videos cannot be found in internat databases, it is recommend
to install exiftool. Once installed, the script will automatically try exiftool
if all other approaches fails. (sudo apt install exiftool)'
EOF
}

invalid_parameter() {
  printf '%s\n' "Invalid parameter: $1" "For more information, type: 'avinfo.sh --help'"
  exit 1
}

# Begin
# Bash Version
[[ "${BASH_VERSINFO[0]}${BASH_VERSINFO[1]}" -ge 42 ]] || {
  printf '%s\n' "Error: The script requires at least bash 4.2 to run, exit."
  exit 1
}

# Dependencies
if ! hash 'awk' 'sed' 'wget' 'iconv'; then
  printf '%s\n' "Lack dependency:" "Something is not installed."
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
    printf '\033[31m%s\033[0m\n%s\n' "Lack of target!" "For more information, type: 'avinfo.sh --help'"
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

printf '%s\n' "$divider_bold"

if [[ -d ${target} ]]; then
  printf '%s\n' "Task start using ${thread:=3} threads."
  case "$mode" in
    "dir")
      handle_dirs "${target}"
      ;;
    "actress")
      export -f handle_actress
      find "${target}" -maxdepth 1 -type d -not -path "*/[@#.]*" -print0 |
        xargs -r -0 -n 1 -P "${thread}" bash -c 'handle_actress "$@"' _
      ;;
    *)
      fifo="${TMPDIR:-/tmp}/avinfo.lock"
      mkfifo "${fifo}"
      trap 'rm -f -- "${fifo}"' EXIT
      exec {fifo_fd}<>"${fifo}"
      printf '%s\n' '1' >&${fifo_fd}

      find "${target}" -type f -not -empty -not -path "*/[@#.]*" -printf '%Ts\0%p\0' |
        xargs -r -0 -n 10 -P "${thread}" awk -v fifo="${fifo}" -f "${script_dir}/handle_files.awk"

      exec {fifo_fd}>&-
      printf '%s\n' "$divider_bold"
      handle_dirs "${target}"
      ;;
  esac
else
  awk -f "${script_dir}/handle_files.awk" "$(date -r "${target}" '+%s')" "${target}"
fi

exit 0
