#!/usr/bin/env bash

export LC_ALL=C.UTF-8 LANG=C.UTF-8 || export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

handle_files() {

  handle_videos() {
    file[basename]="${file[filename]%.*}"
    file[basename]="$(
      sed -E '
        s/\[[a-z0-9\.\-]+\.[a-z]{2,}\]//g;
        s/[^a-z0-9]?(168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|fhd|tokyo[ _-]?hot|1000[ _-]?girl)[^a-z0-9]?//g;
      ' <<<"${file[filename],,}"
    )"

    # carib
    if [[ ${file[basename]} =~ ${regex_start}carib(bean|pr|com)*${regex_end} && ${file[basename]} =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      info[date]="${info[id]:4:2}${info[id]:0:4}"
      if [[ -n ${info[id]} ]]; then
        if [[ ${file[basename]} =~ ${regex_start}carib(bean|com)*pr${regex_end} ]]; then
          tmp[url]='https://www.caribbeancompr.com/moviepages'
          info[id]="${info[id]//-/_}"
        else
          tmp[url]='https://www.caribbeancom.com/moviepages'
        fi
        info[title]="$(
          wget -qO- "${tmp[url]}/${info[id]}/" | iconv -c -f EUC-JP -t UTF-8 | awk '
            /<div class="heading">/ {
              flag = 1
            }
            flag == 1 && match($0, /<h1[^>]*>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/h1>/, m) {
              print m[1]
              exit
            }
          '
        )"
        if [[ -n ${info[title]} ]]; then
          final[date]="$(date -d "${info[date]}" '+%s')"
          if ((final[date])); then
            info[date_source]="Product ID"
            info[title_source]='caribbeancom.com'
            rename_file "get_standard_product_id"
            touch_file && return 0
          fi
        else
          if modify_file_via_database "local" "local" "uncensored"; then return 0; fi
        fi
      fi

    # 1pondo
    elif [[ ${file[basename]} =~ ${regex_start}(1pon(do)?|10mu(sume)?|mura(mura)?|paco(pacomama)?)${regex_end} && ${file[basename]} =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      info[date]="${info[id]:4:2}${info[id]:0:4}"
      if [[ -n ${info[id]} ]] && modify_file_via_database 'local' "local" "uncensored"; then return 0; fi

    # 160122_1020_01_Mesubuta
    elif [[ ${file[basename]} =~ ${regex_start}mesubuta${regex_end} && ${file[basename]} =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})[_-]([0-9]{2,4})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      info[date]="${info[id]%%-*}"
      if [[ -n ${info[id]} ]] && modify_file_via_database 'local' "local" "uncensored"; then return 0; fi

    # HEYZO-0988
    elif [[ ${file[basename]} =~ ${regex_start}(heyzo|jukujo|kin8tengoku)[^0-9]*([0-9]{4})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      modify_file_via_database "query" "query" "uncensored" && return 0

    # honnamatv
    elif [[ ${file[basename]} =~ ${regex_start}honnamatv[^0-9]*([0-9]{3,})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}"
      tmp[name]=honnamatv
      tmp[url]="https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/${info[id]}/index.html"
      heydouga && return 0

    # heydouga-4197-001
    elif [[ ${file[basename]} =~ ${regex_start}hey(douga)?[^a-z0-9]*([0-9]{4})[^a-z0-9]*([0-9]{3,})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[3]}/${BASH_REMATCH[4]}"
      tmp[name]=heydouga
      tmp[url]="https://www.heydouga.com/moviepages/${info[id]}/index.html"
      heydouga && return 0

    # x1x-111815
    elif [[ ${file[basename]} =~ ${regex_start}x1x[[:space:]_-]?([0-9]{6})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}"
      for i in 'info[title]' 'final[date]'; do
        IFS= read -r "${i}"
      done < <(
        wget -qO- "http://www.x1x.com/title/${info[id]}" | awk '
          ! title && match($0, /<title>[^<]+<\/title>/) {
            title = substr($0, RSTART, RLENGTH)
            gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$/, "", title)
          }
          ! date && /配信日/ {
            do {
              if (match($0, /(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) ) {
                date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
                break
              }
            } while (getline > 0)
          }
          title && date { print title; print date ; exit }
        '
      )
      if ((final[date])); then
        if [[ -n ${info[title]} ]]; then
          info[title_source]="x1x.com"
          rename_file "x1x-${info[id]}"
        fi
        info[date_source]="x1x.com"
        touch_file && return 0
      fi

    # h4610, c0930, h0930
    elif [[ ${file[basename]} =~ ${regex_start}(h4610|[ch]0930)[^a-z0-9]+([a-z]+[0-9]+)${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]^^}-${BASH_REMATCH[3]}"
      tmp[name]="${BASH_REMATCH[2]}"
      tmp[url]="https://www.${BASH_REMATCH[2]}.com/moviepages/${BASH_REMATCH[3]}/"
      for i in 'info[title]' 'final[date]'; do
        IFS= read -r "${i}"
      done < <(
        wget -qO- "${tmp[url]}" | iconv -c -f EUC-JP -t UTF-8 | awk '
          ! title && match($0, /<title>[^<]+<\/title>/) {
            title = substr($0, RSTART, RLENGTH)
            gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$/, "", title)
          }
          ! date && /dateCreated|startDate|uploadDate/ {
            do {
              if (match($0, /(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) ) {
                date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
                break
              }
            } while (getline > 0)
          }
          title && date { print title; print date ; exit }
        '
      )
      if ((final[date])); then
        if [[ -n ${info[title]} ]]; then
          info[title_source]="${tmp[name]}.com"
          rename_file "${info[id]}"
        fi
        info[date_source]="${tmp[name]}.com"
        touch_file && return 0
      fi

    # FC2
    elif [[ ${file[basename]} =~ ${regex_start}fc2[[:space:]_-]*(ppv)?[[:space:]_-]+([0-9]{2,10})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[3]}"
      tmp[result]="$(
        wget -qO- "https://adult.contents.fc2.com/article/${info[id]}/" | awk '
          ! title && /<div class="items_article_headerInfo">/ && match($0, /<h3>[^<]+<\/h3>/) {
            title = substr($0, RSTART, RLENGTH)
            gsub(/^<h3>[[:space:]]*|[[:space:]]*<\/h3>$/, "", title)
          }
          ! date && /<div class="items_article_Releasedate">/ && match($0, /<p>[^<:]*:[[:space:]]*(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) {
            date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
          }
          title && date { print title; print date ; exit }'
      )"
      if [[ -z ${tmp[result]} ]]; then
        tmp[result]="$(
          wget -qO- "http://video.fc2.com/a/search/video/?keyword=${info[id]}" | awk '
            match($0, /<a href="https:\/\/video.fc2.com\/a\/content\/([0-9]{4})([0-9]{2})([0-9]{2})+[^"]*" class="[^"]*" title="[^"]+" data-popd>[[:space:]]*([^<]+[^[:space:]<])[[:space:]]*<\/a>/, m) {
              title = m[4]
              date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
            }
            title && date { print title; print date ; exit }
          '
        )"
        if [[ -z ${tmp[result]} ]]; then
          tmp[result]="$(
            wget -qO- "https://fc2club.com/html/FC2-${info[id]}.html" | awk '
              ! title && /<div class="show-top-grids">/ {
                do {
                  if (match($0,/<h3>[^<]+<\/h3>/)) {
                    title = substr($0, RSTART, RLENGTH)
                    gsub(/^<h3>[[:space:]]*(FC2-[[:digit:]]+[[:space:]]*)?|[[:space:]]*<\/h3>$/, "", title)
                    break
                  }
                } while (getline > 0)
              }
              ! date && /<ul class="slides">/ {
                do {
                  if (match($0,/<img class="responsive"[[:space:]]+src="\/uploadfile\/(20[12][0-9])\/(1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])\//,m)) {
                    date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
                    break
                  }
                } while (getline > 0)
              }
              title && date {print title; print date ; exit}
            '
          )"
        fi
      fi

      if [[ -n ${tmp[result]} ]]; then
        for i in 'info[title]' 'final[date]'; do
          IFS= read -r "${i}"
        done <<<"${tmp[result]}"
        if ((final[date])); then
          if [[ -n ${info[title]} ]]; then
            info[title_source]="fc2.com"
            rename_file "FC2-${info[id]}"
          fi
          info[date_source]="fc2.com"
          touch_file && return 0
        fi
      fi

    # sm-miracle
    elif [[ ${file[basename]} =~ ${regex_start}sm([[:space:]_-]miracle)?([[:space:]_-]no)?[[:space:]_\.\-]e?([0-9]{4})${regex_end} ]]; then
      info[id]="e${BASH_REMATCH[4]}"
      info[date]="$(
        wget -qO- "http://sm-miracle.com/movie3.php?num=${info[id]}" |
          grep -Po -m1 '(?<=\/)20[12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])(?=\/top)'
      )"
      [[ -n ${info[date]} ]] && final[date]="$(date -d "${info[date]}" '+%s')"
      if ((final[date])); then
        info[title]="$(
          wget -qO- "http://sm-miracle.com/movie/${info[id]}.dat" |
            sed -En "0,/^[[:space:][:punct:]]*title:[[:space:]\'\"]*([^\"\'\,]+[^[:space:]\"\'\,]).*/s//\1/p"
        )"
        if [[ -n ${info[title]} ]]; then
          info[title_source]="sm-miracle.com"
          rename_file "sm-miracle-${info[id]}"
        fi
        info[date_source]="sm-miracle.com"
        touch_file && return 0
      fi

    # 1000girl
    elif [[ ${file[basename]} =~ ${regex_start}([12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9]))[_-]?([a-z]{3,}(_[a-z]{3,})?)${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[5]}"
      modify_file_via_database "query" "query" "uncensored" && return 0

    # th101-000-123456
    elif [[ ${file[basename]} =~ ${regex_start}(th101)[_-]([0-9]{3})[_-]([0-9]{6})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      modify_file_via_database "query" "query" "uncensored" && return 0

    # mkbd_s24
    elif [[ ${file[basename]} =~ ${regex_start}(mkbd|bd)[[:space:]_-]?([sm]?[0-9]+)${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      modify_file_via_database "query" "query" "uncensored" && return 0

    # tokyo hot
    elif [[ ${file[basename]} =~ ${regex_start}((n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-3][0-9]{3}|(bouga|ka|sr|tr|sky)[0-9]{3,4})${regex_end} ]]; then
      [[ ${file[basename]} =~ ${regex_start}(n|k|kb|jpgc|shiroutozanmai|hamesamurai|bouga|ka|sr|tr|sky)([0-9]{3,4})${regex_end} ]] && info[id]="${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
      if [[ -n ${info[id]} ]] && modify_file_via_database "query" "query" "uncensored"; then return 0; fi

    # club00379hhb
    elif [[ ${file[basename]} =~ ${regex_start}([a-z]+)0{,2}([0-9]{3,4})hhb[0-9]?${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      modify_file_via_database "query" "query" "all" && return 0

      # MX-64
    elif [[ ${file[basename]} =~ (^|\(\)\[\])([a-z]+(3d|3d2|2d|2m)*[a-z]+|xxx[_-]?av)[[:space:]_-]?([0-9]{2,6})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[4]}"
      modify_file_via_database "query" "query" "all" && return 0

    # 111111_111
    elif [[ ${file[basename]} =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
      info[id]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
      modify_file_via_database "query" "query" "uncensored" && return 0

      # 23.Jun.2014
    elif [[ ${file[basename]} =~ ${regex_start}(3[01]|[12][0-9]|0?[1-9])[[:space:],\.\_\-]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[[:space:],\.\_\-]*(20[0-2][0-9])${regex_end} ]]; then
      info[date]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      modify_date_via_string && return 0

      # Dec.23.2014
    elif [[ ${file[basename]} =~ ${regex_start}(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[[:space:],\.\_\-]*(3[01]|[12][0-9]|0?[1-9])[[:space:],\.\_\-]*(20[0-2][0-9])${regex_end} ]]; then
      info[date]="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
      modify_date_via_string && return 0

    # (20)19.03.15
    elif [[ ${file[basename]} =~ ${regex_start}((20)?(2[0-5]|1[0-9]|0[7-9]))[\._\-]?(1[0-2]|0[1-9])[\._\-]?(3[01]|[12][0-9]|0[1-9])${regex_end} ]]; then
      info[date]="${BASH_REMATCH[2]}-${BASH_REMATCH[5]}-${BASH_REMATCH[6]}"
      modify_date_via_string && return 0

    # 23.02.20(19)
    elif [[ ${file[basename]} =~ ${regex_start}(3[01]|[12][0-9]|0[1-9])[\._\-](1[0-2]|0[1-9])[\._\-]((20)?(2[0-5]|1[0-9]|0[7-9]))${regex_end} ]]; then
      info[date]="${BASH_REMATCH[4]}-${BASH_REMATCH[3]}-${BASH_REMATCH[2]}"
      modify_date_via_string && return 0

    fi

    if modify_time_via_exif; then
      return 0
    else
      return 1
    fi
  }

  heydouga() {
    for i in 'info[title]' 'final[date]'; do
      IFS= read -r "${i}"
    done < <(
      wget -qO- "${tmp[url]}" | awk '
        ! title && match($0, /<title>[^<]+<\/title>/) {
          title = substr($0, RSTART, RLENGTH)
          gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$|[[:space:]]*&#45;.*/, "", title)
        }
        ! date && /配信日/ {
          do {
            if (match($0, /(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) ) {
              date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
              break
            }
          } while (getline > 0)
        }
        title && date { print title; print date ; exit }
      '
    )
    if ((final[date])); then
      if [[ -n ${info[title]} ]]; then
        info[title_source]='heydouga.com'
        rename_file "${tmp[name]}-${info[id]//\//-}"
      fi
      info[date_source]='heydouga.com'
      touch_file && return 0
    fi
  }

  modify_file_via_database() {
    # $1: local/query
    # $2: local/query
    # $3: all/uncensored
    local date_strategy="$1" rename_strategy="$2" product_type="$3" match_regex="${info[id]//[_-]/[_-]?}"

    for i in "uncensored/" ""; do
      for n in 'info[product_id]' 'info[title]' 'final[date]'; do
        IFS= read -r "${n}"
      done < <(
        wget -qO- "https://www.javbus.com/${i}search/${info[id]}" |
          awk -v regex="${match_regex}" '
            BEGIN {
              regex = tolower(regex)
            }

            tolower($0) ~ ("<a class=\"movie-box\" href=\"https://www\\.javbus\\.com/" regex "([^a-z0-9][^\"]*)?\">") {
              flag = 1
            }

            flag == 1 && /<div class="photo-info">/ {
              flag = 2
            }

            flag == 2 && match($0, /<span>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<br/, m) {
              flag = 3
              title = m[1]
            }

            flag == 3 && match(tolower($0), "<date>" regex "</date>") {
              flag = 4
              uid = substr($0, RSTART, RLENGTH)
              gsub(/^<date>|<\/date>$/, "", uid)
            }

            flag == 4 && match($0, /(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) {
              date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
              if (uid && title && date) {
                printf "%s\n%s\n%s\n", uid, title, date
                exit
              }
            }
          '
      ) || [[ ${product_type} == "uncensored" ]] && break
    done
    if [[ ${info[product_id]} ]]; then
      info[date_source]='javbus.com'
      info[title_source]='javbus.com'
    else
      for n in 'info[product_id]' 'info[title]' 'final[date]'; do
        IFS= read -r "${n}"
      done < <(
        wget -qO- "https://javdb.com/search?q=${info[id]}&f=all" |
          awk -v regex="${match_regex}" '
            BEGIN { regex=tolower(regex) }
            match(tolower($0), "<div class=\"uid\">[[:space:]]*" regex "[[:space:]]*</div>") {
              flag=1
              uid=substr($0, RSTART, RLENGTH)
              gsub(/^<div class="uid">[[:space:]]*|[[:space:]]*<\/div>$/, "", uid)
            }
            flag == 1 && match($0, /<div class="video-title">[^<]+<\/div>/) {
              flag=2
              title = substr($0, RSTART, RLENGTH)
              gsub(/^<div class="video-title">[[:space:]]*|[[:space:]]*<\/div>$/, "", title)
            }
            flag == 2 && /<div class="meta">/ {flag=3}
            flag == 3 && match($0, /(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) {
              date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
              if (uid && title && date) { printf "%s\n%s\n%s\n", uid, title, date ; exit }
            }
          '
      )
      if [[ ${info[product_id]} ]]; then
        info[date_source]='javdb.com'
        info[title_source]='javdb.com'
      else
        for n in 'info[product_id]' 'info[title]' 'final[date]'; do
          IFS= read -r "${n}"
        done < <(
          wget -qO- --post-data "sn=${info[id]}" 'https://www.jav321.com/search' | awk '
              /<div class="panel-heading">/,// {
                if ( ! title && match($0, /<h3>[^<]+</) ) {
                  title = substr($0, RSTART, RLENGTH)
                  gsub(/^<h3>[[:space:]]*|[[:space:]]*<$/, "", title)
                }
                if ( ! uid && match($0, /<b>番号<\/b>[^<]+/) ) {
                  uid = substr($0, RSTART, RLENGTH)
                  gsub(/^<b>番号<\/b>[[:space:]:]*|[[:space:]]*$/, "", uid)
                }
                if ( ! date && match($0, /<b>发行日期<\/b>[[:space:]:]*(20[0-3][0-9])[\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/, m) ) {
                  date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
                }
                if (uid && title && date) { printf "%s\n%s\n%s\n", toupper(uid), title, date ; exit }
              }
            '
        )
        if [[ ${info[product_id]} ]]; then
          info[date_source]='jav321.com'
          info[title_source]='jav321.com'
        fi
      fi
    fi

    if [[ ${info[title]} ]]; then
      case "${rename_strategy}" in
        "local")
          rename_file "get_standard_product_id"
          ;;
        "query")
          rename_file "${info[product_id]}"
          ;;
      esac
    fi

    if [[ ${date_strategy} == 'local' ]]; then
      final[date]="$(date -d "${info[date]}" '+%s')"
      info[date_source]="Product ID"
    fi

    if ((final[date])) && touch_file; then
      return 0
    else
      return 1
    fi
  }

  modify_date_via_string() {
    final[date]="$(date -d "${info[date]}" '+%s')"
    if ((final[date])); then
      info[date_source]="File name"
      touch_file && return 0
    fi
    return 1
  }

  modify_time_via_exif() {
    if ((exiftool_installed)); then
      final[date]="$(
        exiftool -api largefilesupport=1 -Creat*Date -ModifyDate -Track*Date -Media*Date -Date*Original -d "%s" -S -s "${target_file}" 2>/dev/null |
          awk '$0 != "" && $0 !~ /^0000/ {print;exit}'
      )"
      if ((final[date])); then
        info[date_source]='Exif'
        touch_file && return 0
      fi
    fi
    return 1
  }

  rename_file() {
    if [[ $1 == "get_standard_product_id" ]]; then
      final[product_id]="$(get_standard_product_id <<<"${file[basename]}")"
    else
      final[product_id]="$1"
      [[ ${file[basename]} =~ ${info[id]//[\/_-]/[^a-z0-9]?}[[:space:]_-](c|(2160|1080|720|480)p|(high|mid|low|whole|hd|sd|cd|psp)?[[:space:]_-]?[0-9]{1,2})([[:space:]_-]|$) ]] &&
        final[product_id]="${final[product_id]}-${BASH_REMATCH[1]}"
    fi

    final[filename]="$(
      sed -E '
        s/[[:space:]<>:"/\|?* 　]/ /g;
        s/[[:space:]\._\-]{2,}/ /g;
        s/^[[:space:]\.\-]+|[[:space:]\.,\-]+$//g;
      ' <<<"${final[product_id]} ${info[title]}"
    )"

    local name_tmp
    while (("$(printf '%s' "${final[filename]}${file[ext]}" | wc -c)" >= max_length)); do
      name_tmp="${final[filename]%[[:space:]]*}"

      while [[ ${name_tmp} == "${final[product_id]}" ]]; do
        final[filename]="${final[filename]:0:$((${#final[filename]} - 1))}"
        (("$(printf '%s' "${final[filename]}${file[ext]}" | wc -c)" < max_length)) && break 2
      done

      final[filename]="${name_tmp}"
    done

    final[filename]="${final[filename]}${file[ext]}"

    if [[ ${final[filename]} != "${file[filename]}" ]]; then
      final[fullpath]="${file[parentdir]}/${final[filename]}"
      if ((real_run)); then
        if ! mv "${file[fullpath]}" "${final[fullpath]}"; then
          unset 'final[fullpath]'
          return 1
        fi
      fi
      final[title_changed]=1
    fi
  }

  touch_file() {
    if ((file[date] != final[date])); then
      if ((real_run)); then
        if ! touch -d "@${final[date]}" "${final[fullpath]:-${file[fullpath]}}"; then
          return 1
        fi
      fi
      final[date_changed]=1
    fi
    return 0
  }

  get_standard_product_id() {
    awk '
    {
      org = $0
      $0 = tolower($0)
      gsub(/[[:space:]\]\[)(}{._-]+/, " ", $0)
      for (i = 1; i <= NF; i++) {
        if (! id) {
          if ($0 ~ /mesubuta/) {
            if ($i ~ /^[0-9]{6}$/ && $(i + 1) ~ /^[0-9]{2,5}$/ && $(i + 2) ~ /^[0-9]{1,3}$/) {
              id = ($i "_" $(i + 1) "_" $(i + 2))
              i += 2
              flag = 1; continue
            }
          } else if ($i ~ /^[0-9]{6}$/ && $(i + 1) ~ /^[0-9]{2,6}$/) {
            id = ($i "_" $(i + 1))
            i++
            flag = 1; continue
          }
        }
        if (! studio) {
          if ($i ~ /^1pon(do)?$/) {
            studio = "-1pon"
            flag = 1; continue
          } else if ($i ~ /^10mu(sume)?$/) {
            studio = "-10mu"
            flag = 1; continue
          } else if ($i ~ /^carib(bean|com)*$/) {
            studio = "-carib"
            flag = 1; continue
          } else if ($i ~ /^carib(bean|com)*pr$/) {
            studio = "-caribpr"
            flag = 1; continue
          } else if ($i ~ /^mura(mura)?$/) {
            studio = "-mura"
            flag = 1; continue
          } else if ($i ~ /^paco(pacomama)?$/) {
            studio = "-paco"
            flag = 1; continue
          } else if ($i ~ /^mesubuta$/) {
            studio = "-mesubuta"
            flag = 1; continue
          }
        }
        if (flag && $i ~ /^((2160|1080|720|480)p|(high|mid|low|whole|hd|sd|psp)[0-9]*|[0-9])$/) {
          other = (other "-" $i)
        } else {
          flag = 0
        }
      }
      if (id && studio) {
        print id studio other
      } else {
        print org
      }
    }'
  }

  output() {
    local final_date_display divider_format divider title_format date_format

    case $1 in
      success)
        divider='------------------ SUCCESS --------------------'
        ;;
      failed)
        divider_format='\033[31m%s\033[0m'
        divider='------------------ FAILED  --------------------'
        ;;
    esac

    ((final[date])) && printf -v final_date_display '%(%F %T)T' "${final[date]}"

    (
      flock -x "${fd}"

      ((final[title_changed])) && {
        title_format='\033[93m%s\033[0m'
        ((real_run)) && printf "[%(%F %T)T] %s\n%15s: %s\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n" \
          "-1" "Rename:" \
          "Original path" "${file[fullpath]}" \
          "New name" "${final[filename]}" \
          "Title" "${info[title]}" \
          "Source" "${info[title_source]}" \
          "${divider_slim}" >&${fd}
      }

      ((final[date_changed])) && {
        date_format='\033[93m%s\033[0m'
        ((real_run)) && printf "[%(%F %T)T] %s\n%15s: %s\n%15s: %(%F %T)T\n%15s: %s\n%15s: %s\n%s\n" \
          "-1" "Change Date:" \
          "Path" "${final[fullpath]:-${file[fullpath]}}" \
          "Original date" "${file[date]}" \
          "New date" "${final_date_display}" \
          "Source" "${info[date_source]}" \
          "${divider_slim}" >&${fd}
      }

      printf "${divider_format:-%s}\n%10s %s\n%10s ${title_format:-%s}\n%10s ${date_format:-%s}\n%10s %s\n" \
        "${divider}" \
        "File:" "${final[filename]:-${file[filename]}}" \
        "Title:" "${info[title]:----}" \
        "Date:" "${final_date_display:----}" \
        "Source:" "${info[date_source]:----} / ${info[title_source]:----}"
    )
  }

  # Begins Here
  regex_start='(^|[^a-z0-9])'
  regex_end='([^a-z0-9]|$)'

  exec {fd}>>"${log_file}"

  while (($# > 0)); do
    declare -A file=(
      [date]="${1}"
      [fullpath]="${2}"
      [filename]="${2##*/}"
      [parentdir]="${2%/*}"
      [basename]=''
      [ext]=''
    ) info=(
      [id]=''
      [product_id]=''
      [date]=''
      [title]=''
      [date_source]=''
      [title_source]=''
    ) final=(
      [date]=''
      [product_id]=''
      [filename]=''
      [fullpath]=''
      [date_changed]=0
      [title_changed]=0
    ) tmp=()

    [[ ${file[filename]##*.} != "${file[filename]}" ]] && file[ext]=".${file[filename]##*.}" && file[ext]="${file[ext],,}"

    case "${file[ext]}" in
      .3gp | .asf | .avi | .flv | .m2ts | .m2v | .m4p | .m4v | .mkv | .mov | .mp2 | .mp4 | .mpeg | .mpg | .mpv | .mts | .mxf | .rm | .rmvb | .ts | .vob | .webm | .wmv | .iso)
        if handle_videos; then
          output "success"
        else
          output "failed"
        fi
        ;;
      *)
        if modify_time_via_exif; then
          output "success"
        else
          output "failed"
        fi
        ;;
    esac

    shift 2
  done

  exec {fd}>&-
}

handle_dirs() {
  awk -v real_run="${real_run}" -v log_file="${log_file}" -v divider_slim="${divider_slim}" -v divider_bold="${divider_bold}" -v root_dir="${1}" '
  BEGIN {
    FS = OFS = "/"
    RS = "\000"
    count = success_count = 0
    root_length = length(root_dir)
    print "Scanning directories..."
    printf "%s\n%7s   %-7s   %-10s   %s\n%s\n", divider_slim, "Number", "Result", "Date", "Directory", divider_slim
  }

  /^[0-9]+\/[df]$/ {
    file_date = $1
    file_type = $2
    if ((getline) <= 0) {
      next
    }
    if (file_type == "f") {
      for (NF = NF - 1; length($0) >= root_length; NF--) {
        if (file_date > date[$0]) {
          date[$0] = file_date
        }
      }
    } else if (date[$0] && date[$0] != file_date) {
      if (real_run) {
        ENVIRON["touch_dir"] = $0
        if (system("touch -d \047@" date[$0] "\047 \"${touch_dir}\"") == 0) {
          printf ("[%s] %s\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n",
            strftime("%F %T"), "Change Dir Date",
            "Path", $0,
            "Original date", strftime("%F %T",file_date),
            "New date", strftime("%F %T",date[$0]),
            divider_slim) >> log_file
        }
      }
      printf "\033[93m%7s   %-7s   %-10s   %s\033[0m\n", ++count, "Success", strftime("%F", date[$0]), $NF
      success_count++
    } else {
      printf "%7s   %-7s   %-10s   %s\n", ++count, "Skipped", strftime("%F", file_date), $NF
    }
  }

  END {
    print divider_slim
    print "Finished."
    print success_count " dirs modified."
    print (count - success_count) " dirs untouched."
    print divider_bold
  }

  ' <(find "$1" -depth -type 'd,f' -not -empty -not -path "*/[@#.]*" -printf '%Ts/%y\0%p\0')
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
          } {fd}>>"${log_file}"
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
                      default number is 5 if not specified.
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
if ! hash 'awk' 'sed' 'grep' 'wget' 'flock' 'iconv'; then
  printf '%s\n' "Lack dependency:" "Something is not installed."
  exit 1
fi

# Awk Version
awk 'BEGIN { if (PROCINFO["version"] >= 4.2) exit 0; else exit 1 }' || {
  printf '%s\n' "Error: The script requires GNU Awk 4.2+ to run, please make sure gawk is properly installed and configed as default." 1>&2
  exit 1
}

printf -v divider_bold '%0*s' "47" ""
declare -xr log_file="$(cd "${BASH_SOURCE[0]%/*}" && pwd -P)/log.log" divider_bold="${divider_bold// /=}" divider_slim="${divider_bold// /-}"
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
          if [[ -z ${TARGET} ]]; then
            TARGET="${1%/}"
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
  if [[ -z ${TARGET} ]]; then
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
max_length="$(stat -f -c '%l' "${TARGET}")"
[[ ${max_length} =~ ^[0-9]+$ ]] || max_length=255
declare -rx max_length

printf '%s\n' "$divider_bold"

if [[ -d ${TARGET} ]]; then
  printf '%s\n' "Task start using ${thread:=5} threads."
  case "$mode" in
    "dir")
      handle_dirs "${TARGET}"
      ;;
    "actress")
      export -f handle_actress
      find "${TARGET}" -maxdepth 1 -type d -not -path "*/[@#.]*" -print0 | xargs -r -0 -n 1 -P "${thread}" bash -c 'handle_actress "$@"' _
      ;;
    *)
      export -f handle_files
      find "${TARGET}" -type f -not -empty -not -path "*/[@#.]*" -printf '%Ts\0%p\0' | xargs -r -0 -n 10 -P "${thread}" bash -c 'handle_files "$@"' _
      printf '%s\n' "$divider_bold"
      handle_dirs "${TARGET}"
      ;;
  esac
else
  handle_files "$(date -r "${TARGET}" '+%s')" "${TARGET}"
fi

exit 0
