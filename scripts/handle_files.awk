#!/usr/bin/awk -f

BEGIN {
  real_run = (ENVIRON["real_run"] ? 1 : 0)
  exiftool_installed = (ENVIRON["exiftool_installed"] ? 1 : 0)
  max_length = ENVIRON["max_length"]
  logfile = ENVIRON["logfile"]
  divider_slim = ENVIRON["divider_slim"]

  split("jan feb mar apr may jun jul aug sep oct nov dec", m, " ")
  for (i = 1; i <= 12; i++) month[m[i]] = i

  for (arg = 1; arg < ARGC; arg += 2) {
    delete file
    delete info
    delete final
    delete tmp

    file["date"] = ARGV[arg]
    file["fullpath"] = ARGV[arg + 1]
    file["filename"] = gensub(/^.*\//, "", "1", file["fullpath"])
    file["parentdir"] = gensub(/\/[^\/]+$/, "", "1", file["fullpath"])
    file["ext"] = gensub(/^.*\./, "", "1", file["filename"])

    if (file["ext"] == file["filename"]) {
      file["ext"] = ""
    } else {
      file["ext"] = ("." tolower(file["ext"]))
    }

    ENVIRON["target_file"] = file["fullpath"]

    if (file["ext"] ~ /^\.(3gp|asf|avi|flv|m2ts|m2v|m4p|m4v|mkv|mov|mp2|mp4|mpeg|mpg|mpv|mts|mxf|rm|rmvb|ts|vob|webm|wmv|iso)$/) {
      if (handle_videos()) {
        output(1)
      } else {
        output(0)
      }
    } else if (modify_time_via_exif()) {
      output(1)
    } else {
      output(0)
    }
  }
}


function bytes_length(string,   cmd, i)
{
  cmd = "wc -c"
  printf("%s", string) |& cmd
  close(cmd, "to")
  cmd |& getline i
  close(cmd)
  return i
}

function get_standard_product_id(input,    mesubuta, m, n, i, flag, nextfield, id, studio, other)
{
  if (input ~ /mesubuta/) {
    mesubuta = 1
  }
  n = split(tolower(input), m, /[[:space:]\]\[)(}{._-]+/)
  for (i = 1; i <= n; i++) {
    nextfield = 0
    while (id == "") {
      if (mesubuta && m[i] ~ /^[0-9]{6}$/ && m[i + 1] ~ /^[0-9]{2,5}$/ && m[i + 2] ~ /^[0-9]{1,3}$/) {
        id = (m[i] "_" m[i + 1] "_" m[i + 2])
        i += 2
      } else if (! mesubuta && m[i] ~ /^[0-9]{6}$/ && m[i + 1] ~ /^[0-9]{2,6}$/) {
        id = (m[i] "_" m[i + 1])
        i++
      } else {
        break
      }
      flag = 1
      nextfield = 1
    }
    if (nextfield) {
      continue
    }
    while (studio == "") {
      if (m[i] ~ /^1pon(do)?$/) {
        studio = "-1pon"
      } else if (m[i] ~ /^10mu(sume)?$/) {
        studio = "-10mu"
      } else if (m[i] ~ /^carib(bean|com)*$/) {
        studio = "-carib"
      } else if (m[i] ~ /^carib(bean|com)*pr$/) {
        studio = "-caribpr"
      } else if (m[i] ~ /^mura(mura)?$/) {
        studio = "-mura"
      } else if (m[i] ~ /^paco(pacomama)?$/) {
        studio = "-paco"
      } else if (m[i] ~ /^mesubuta$/) {
        studio = "-mesubuta"
      } else {
        break
      }
      flag = 1
      nextfield = 1
    }
    if (nextfield) {
      continue
    }
    if (flag && m[i] ~ /^((2160|1080|720|480)p|(high|mid|low|whole|hd|sd|psp)[0-9]*|[0-9])$/) {
      other = (other "-" m[i])
    } else {
      flag = 0
    }
  }
  if (id != "" && studio != "") {
    return (id studio other)
  } else {
    return input
  }
}

function append_video_suffix(new_id,old_id,   regex, m)
{
  regex = gensub(/[\/_-]/, "[^a-z0-9]?", "g", old_id)
  if (match(file["basename"], (regex "[[:space:]_-](c|(2160|1080|720|480)p|(high|mid|low|whole|hd|sd|cd|psp)?[[:space:]_-]?[0-9]{1,2})([[:space:]_-]|$)"), m)) {
    if (m[1] == "c") m[1] = "C"
    return (new_id "-" m[1])
  } else {
    return new_id
  }
}

function handle_videos(   m, cmd)
{

  file["basename"] = gensub(/\.[^.]*$/, "", "1", tolower(file["filename"]))
  gsub(/\[[a-z0-9\.\-]+\.[a-z]{2,}\]/, "_", file["basename"])
  gsub(/(^|[^a-z0-9])(168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|fhd|tokyo[ _-]?hot|1000[ _-]?girl)([^a-z0-9]|$)/, "_", file["basename"])

  # carib
  if (file["basename"] ~ /(^|[^a-z0-9])carib(bean|pr|com)*([^a-z0-9]|$)/ &&
    match(file["basename"], /(^|[^a-z0-9])([0-9]{2})([0-9]{2})([0-9]{2})[_-]([0-9]{2,4})([^a-z0-9]|$)/, m)) {

    info["id"] = (m[2] m[3] m[4] "-" m[5])
    info["date"] = mktime("20" m[4] " " m[2] " " m[3] " 00 00 00")

    if (file["basename"] ~ /(^|[^a-z0-9])carib(bean|com)*pr([^a-z0-9]|$)/) {
      tmp["url"] = "https://www.caribbeancompr.com/moviepages"
      gsub("-", "_", info["id"])
    } else {
      tmp["url"] = "https://www.caribbeancom.com/moviepages"
    }

    cmd = ("wget -qO- '" tmp["url"] "/" info["id"] "/' | iconv -c -f EUC-JP -t UTF-8")
    while ((cmd | getline) > 0) {
      if ($0 ~ /<div class="heading">/) {
        tmp["flag"] = 1
      }
      if (tmp["flag"] && match($0, /<h1[^>]*>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/h1>/, m)) {
        close(cmd)
        tmp["title"] = m[1]
        rename_file(get_standard_product_id(file["basename"]), tmp["title"], "Caribbeancom.com")
        if (touch_file(info["date"], "Product ID")) return 1
        break
      }
    }
    close(cmd)
    if (modify_file_via_database("local", "local", "uncensored")) return 1

  # 1pondo
  } else if (file["basename"] ~ /(^|[^a-z0-9])(1pon(do)?|10mu(sume)?|mura(mura)?|paco(pacomama)?)([^a-z0-9]|$)/ &&
      match(file["basename"], /(^|[^a-z0-9])([0-9]{2})([0-9]{2})([0-9]{2})[_-]([0-9]{2,4})([^a-z0-9]|$)/, m)) {

    info["id"] = (m[2] m[3] m[4] "-" m[5])
    info["date"] = mktime("20" m[4] " " m[2] " " m[3] " 00 00 00")
    if (modify_file_via_database("local", "local", "uncensored")) return 1

  # 160122_1020_01_Mesubuta
  } else if (file["basename"] ~ /(^|[^a-z0-9])mesubuta([^a-z0-9]|$)/ &&
      match(file["basename"], /(^|[^a-z0-9])([0-9]{2})([0-9]{2})([0-9]{2})[_-]([0-9]{2,4})[_-]([0-9]{2,4})([^a-z0-9]|$)/, m)) {

    info["id"] = (m[2] m[3] m[4] "-" m[5] "-" m[6])
    info["date"] = mktime("20" m[2] " " m[3] " " m[4] " 00 00 00")
    if (modify_file_via_database("local", "local", "uncensored")) return 1

  # HEYZO-0988
  } else if (match(file["basename"], /(^|[^a-z0-9])(heyzo|jukujo|kin8tengoku)[^0-9]*([0-9]{4})([^a-z0-9]|$)/, m)) {

    info["id"] = (m[2] "-" m[3])
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # honnamatv
  } else if (match(file["basename"], /(^|[^a-z0-9])honnamatv[^0-9]*([0-9]{3,})([^a-z0-9]|$)/, m)) {
    info["id"] = m[2]
    tmp["name"] = "honnamatv"
    tmp["url"] = ("https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/" info["id"] "/index.html")
    if (heydouga()) return 1

  # heydouga-4197-001
  } else if (match(file["basename"], /(^|[^a-z0-9])hey(douga)?[^a-z0-9]*([0-9]{4})[^a-z0-9]*([0-9]{3,})([^a-z0-9]|$)/, m)) {
    info["id"] = (m[3] "-" m[4])
    tmp["name"] = "heydouga"
    tmp["url"] = ("https://www.heydouga.com/moviepages/" m[3] "/" m[4] "/index.html")
    if (heydouga()) return 1

  # x1x-111815
  } else if (match(file["basename"], /(^|[^a-z0-9])x1x[[:space:]_-]?([0-9]{6})([^a-z0-9]|$)/, m)) {
    info["id"] = m[2]
    cmd = ("wget -qO- 'www.x1x.com/title/" info["id"] "'")
    while ((cmd | getline) > 0) {
      if (tmp["title"] == "" && match($0, /<title>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/title>/, m)) {
        tmp["title"] = m[1]
      }
      if (! tmp["date"] && $0 ~ /配信日/) {
        do {
          if (match($0, /(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
            tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
            break
          }
        } while ((cmd | getline) > 0)
      }
      if (tmp["title"] != "" && tmp["date"]) {
        close(cmd)
        rename_file(append_video_suffix("x1x-" info["id"], info["id"]), tmp["title"], "x1x.com")
        if (touch_file(tmp["date"], "x1x.com")) return 1
        break
      }
    }
    close(cmd)

  # h4610, c0930, h0930
  } else if (match(file["basename"], /(^|[^a-z0-9])(h4610|[ch]0930)[^a-z0-9]+([a-z]+[0-9]+)([^a-z0-9]|$)/, m)) {
    info["id"] =( toupper(m[2]) "-" m[3])
    tmp["source"] = (m[2] ".com")

    cmd = "wget -qO- 'https://www." m[2] ".com/moviepages/" m[3] "/' | iconv -c -f EUC-JP -t UTF-8"
    while ((cmd | getline) > 0) {
      if (tmp["title"] == "" && match($0, /<title>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/title>/, m)) {
        tmp["title"] = m[1]
      }
      if (! tmp["date"] && $0 ~ /dateCreated|startDate|uploadDate/) {
        do {
          if (match($0, /(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
            tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
            break
          }
        } while ((cmd | getline) > 0)
      }
      if (tmp["title"] != "" && tmp["date"]) {
        close(cmd)
        rename_file(append_video_suffix(info["id"], tolower(info["id"])), tmp["title"], tmp["source"])
        if (touch_file(tmp["date"], tmp["source"])) return 1
        break
      }
    }
    close(cmd)

  # FC2
  } else if (match(file["basename"], /(^|[^a-z0-9])fc2[[:space:]_-]*(ppv)?[[:space:]_-]+([0-9]{2,10})([^a-z0-9]|$)/, m)) {

    info["id"] = m[3]
    cmd = ("wget -qO- 'https://adult.contents.fc2.com/article/" info["id"] "/'")
    while ((cmd | getline) > 0) {
      if (tmp["title"] == "" && $0 ~ /<div class="items_article_headerInfo">/ && match($0, /<h3>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/h3>/, m)) {
        tmp["title"] = m[1]
      }
      if (! tmp["date"] && $0 ~ /<div class="items_article_Releasedate">/ &&
        match($0, /<p>[^<:]*:[[:space:]]*(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
        tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
      }
      if (tmp["title"] != "" && tmp["date"]) {
        close(cmd)
        rename_file(append_video_suffix("FC2-" info["id"], info["id"]), tmp["title"], "fc2.com")
        if (touch_file(tmp["date"], "fc2.com")) return 1
        break
      }
    }
    close(cmd)
    delete tmp

    cmd = ("wget -qO- 'http://video.fc2.com/a/search/video/?keyword=" info["id"] "'")
    while ((cmd | getline) > 0) {
      if (match($0, /<a href="https:\/\/video.fc2.com\/a\/content\/([0-9]{4})([0-9]{2})([0-9]{2})+[^"]*" class="[^"]*" title="[^"]+" data-popd>[[:space:]]*([^<]+[^[:space:]<])[[:space:]]*<\/a>/, m)) {
        tmp["title"] = m[4]
        tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
      }
      if (tmp["title"] != "" && tmp["date"]) {
        close(cmd)
        rename_file(append_video_suffix("FC2-" info["id"], info["id"]), tmp["title"], "fc2.com")
        if (touch_file(tmp["date"], "fc2.com")) return 1
        break
      }
    }
    close(cmd)
    delete tmp

    cmd = ("wget -qO- 'https://fc2club.com/html/FC2-" info["id"] ".html'")
    while ((cmd | getline) > 0) {
      if (tmp["title"] == "" && $0 ~ /<div class="show-top-grids">/) {
        do {
          if (match($0, /<h3>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/h3>/, m)) {
            tmp["title"] = m[1]
            sub(/^FC2-[[:digit:]]+[[:space:]]*/, "", tmp["title"])
            break
          }
        } while ((cmd | getline) > 0)
      }
      if (! tmp["date"] && $0 ~ /<ul class="slides">/) {
        do {
          if (match($0, /<img class="responsive"[[:space:]]+src="\/uploadfile\/(20[12][0-9])\/(1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])\//, m)) {
            tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
            break
          }
        } while ((cmd | getline) > 0)
      }
      if (tmp["title"] != "" && tmp["date"]) {
        close(cmd)
        rename_file(append_video_suffix("FC2-" info["id"], info["id"]), tmp["title"], "fc2club.com")
        if (touch_file(tmp["date"], "fc2club.com")) return 1
        break
      }
    }
    close(cmd)

  # sm-miracle
  } else if (match(file["basename"], /(^|[^a-z0-9])sm([[:space:]_-]miracle)?([[:space:]_-]no)?[[:space:]_\.\-]e?([0-9]{4})([^a-z0-9]|$)/, m)) {
    info["id"] = m[4]
    cmd = ("wget -qO- 'http://sm-miracle.com/movie3.php?num=e" info["id"] "'")
    while ((cmd | getline) > 0) {
      if (match($0, /\/(20[12][0-9])(1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])\/top/, m)) {
        tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
        break
      }
    }
    close(cmd)
    if (tmp["date"]) {
      cmd = ("wget -qO- 'http://sm-miracle.com/movie/e" info["id"] ".dat'")
      while ((cmd | getline) > 0) {
        if (match($0, /^[[:space:][:punct:]]*title:[[:space:]"']*([^"',]+[^[:space:]"',])/, m)) {
          tmp["title"] = m[1]
          close(cmd)
          rename_file(append_video_suffix("sm-miracle-e" info["id"], info["id"]), tmp["title"], "sm-miracle.com")
          if (touch_file(tmp["date"], "sm-miracle.com")) return 1
          break
        }
      }
      close(cmd)
    }

  # 1000girl
  } else if (match(file["basename"], /(^|[^a-z0-9])([12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9]))[_-]?([a-z]{3,}(_[a-z]{3,})?)([^a-z0-9]|$)/, m)) {
    info["id"] = (m[2] "-" m[5])
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # th101-000-123456
  } else if (match(file["basename"], /(^|[^a-z0-9])(th101)[_-]([0-9]{3})[_-]([0-9]{6})([^a-z0-9]|$)/, m)) {
    info["id"] = m[2] "-" m[3] "-" m[4]
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # mkbd_s24
  } else if (match(file["basename"], /(^|[^a-z0-9])(mkbd|bd)[[:space:]_-]?([sm]?[0-9]+)([^a-z0-9]|$)/, m)) {
    info["id"] = m[2] "-" m[3]
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # tokyo hot
  } else if (file["basename"] ~ /(^|[^a-z0-9])((n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-3][0-9]{3}|(bouga|ka|sr|tr|sky)[0-9]{3,4})([^a-z0-9]|$)/ && match(file["basename"], /(^|[^a-z0-9])(n|k|kb|jpgc|shiroutozanmai|hamesamurai|bouga|ka|sr|tr|sky)([0-9]{3,4})([^a-z0-9]|$)/, m)) {
    info["id"] = (m[2] m[3])
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # club00379hhb
  } else if (match(file["basename"], /(^|[^a-z0-9])([a-z]+)0{,2}([0-9]{3,4})hhb[0-9]?([^a-z0-9]|$)/, m)) {
    info["id"] = (m[2] "-" m[3])
    if (modify_file_via_database("query", "query", "all")) return 1

  # MX-64
  } else if (match(file["basename"], /(^|\(\)\[\])([a-z]+(3d|3d2|2d|2m)*[a-z]+|xxx[_-]?av)[[:space:]_-]?([0-9]{2,6})([^a-z0-9]|$)/, m)) {
    info["id"] = (m[2] "-" m[4])
    if (modify_file_via_database("query", "query", "all")) return 1

  # 111111_111
  } else if (match(file["basename"], /(^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})([^a-z0-9]|$)/, m)) {
    info["id"] = (m[2] "-" m[3])
    if (modify_file_via_database("query", "query", "uncensored")) return 1

  # 23.Jun.2014
  } else if (match(file["basename"], /(^|[^a-z0-9])(3[01]|[12][0-9]|0?[1-9])[[:space:],._-]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[[:space:],._-]*(20[0-2][0-9])([^a-z0-9]|$)/, m)) {
    info["date"] = mktime(m[4] " " month[m[3]] " " m[2] " 00 00 00")
    if (modify_date_via_string(info["date"])) return 1

  # Dec.23.2014
  } else if (match(file["basename"], /(^|[^a-z0-9])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[[:space:],._-]*(3[01]|[12][0-9]|0?[1-9])[[:space:],._-]*(20[0-2][0-9])([^a-z0-9]|$)/, m)) {
    info["date"] = mktime(m[4] " " month[m[2]] " " m[3] " 00 00 00")
    if (modify_date_via_string(info["date"])) return 1

  # (20)19.03.15
  } else if (match(file["basename"], /(^|[^a-z0-9])((20)?(2[0-5]|1[0-9]|0[7-9]))[\._\-]?(1[0-2]|0[1-9])[\._\-]?(3[01]|[12][0-9]|0[1-9])([^a-z0-9]|$)/, m)) {
    if (length(m[2]) == 2) m[2] = "20" m[2]
    info["date"] = mktime(m[2] " " m[5] " " m[6] " 00 00 00")
    if (modify_date_via_string(info["date"])) return 1

  # 23.02.20(19)
  } else if (match(file["basename"], /(^|[^a-z0-9])(3[01]|[12][0-9]|0[1-9])[\._\-](1[0-2]|0[1-9])[\._\-]((20)?(2[0-5]|1[0-9]|0[7-9]))([^a-z0-9]|$)/, m)) {
    if (length(m[4]) == 2) m[4] = "20" m[4]

    info["date"] = mktime(m[4] " " m[3] " " m[2] " 00 00 00")
    if (modify_date_via_string(info["date"])) return 1
  }

  if (modify_time_via_exif()) {
    return 1
  } else {
    return 0
  }
}

function heydouga(   flag, m, cmd)
{
  cmd = ("wget -qO- '" tmp["url"] "'")
  while ((cmd | getline) > 0) {
    if (tmp["title"] == "" && match($0, /<title>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/title>/, m)) {
      tmp["title"] = m[1]
      sub(/[[:space:]]*&#45;.*$/, "", tmp["title"])
    }
    if (! tmp["date"] && $0 ~ /配信日/) {
      flag = 1
    }
    if (flag && match($0, /(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
      tmp["date"] = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
    }
    if (tmp["title"] != "" && tmp["date"]) {
      close(cmd)
      rename_file(append_video_suffix(tmp["name"] "-" info["id"], info["id"]), tmp["title"], "heydouga.com")
      if (touch_file(tmp["date"], "heydouga.com")) return 1
      break
    }
  }
  close(cmd)
  return 0
}

function jav321(   flag, uid, title, date, m)
{
  cmd = ("wget -qO- --post-data 'sn=" tolower(info["id"]) "' 'https://www.jav321.com/search'")
  while ((cmd | getline) > 0) {
    if ($0 ~ /<div class="panel-heading">/) {
      flag = 1
    }
    if (flag == 1) {
      if (title == "" && match($0, /<h3>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*</, m)) {
        title = m[1]
      }
      if (uid == "" && match($0, /<b>番号<\/b>[[:space:]]*([^<]*[^[:space:]<])/, m)) {
        uid = m[1]
      }
      if (date == "" && match($0, /<b>发行日期<\/b>[[:space:]:]*(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
        date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
        if (query_database_return(uid, title, date, "jav321.com")) {
          return 1
        }
      }
    }
  }
  close(cmd)
  return 0
}

function javbus(prefix,    flag, uid, title, date, m)
{
  cmd = ("wget -qO- 'https://www.javbus.com/" prefix "search/" tolower(info["id"]) "'")
  while ((cmd | getline) > 0) {
    if (tolower($0) ~ ("<a class=\"movie-box\" href=\"https://www\\.javbus\\.com/" tmp["match_regex"] "([^a-z0-9][^\"]*)?\">")) {
      flag = 1
    }
    if (flag == 1 && /<div class="photo-info">/) {
      flag = 2
    }
    if (flag == 2 && match($0, /<span>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<br/, m)) {
      flag = 3
      title = m[1]
    }
    if (flag == 3 && match(tolower($0), "<date>" tmp["match_regex"] "</date>")) {
      flag = 4
      uid = substr($0, RSTART, RLENGTH)
      gsub(/^<date>|<\/date>$/, "", uid)
    }
    if (flag == 4 && match($0, /(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
      date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
      if (query_database_return(uid, title, date, "javbus.com")) {
        return 1
      }
    }
  }
  close(cmd)
  return 0
}

function javdb(   flag, uid, title, date, m)
{
  cmd = ("wget -qO- 'https://javdb.com/search?q=" tolower(info["id"]) "&f=all'")
  while ((cmd | getline) > 0) {
    if (match(tolower($0), "<div class=\"uid\">[[:space:]]*" tmp["match_regex"] "[[:space:]]*</div>")) {
      flag = 1
      uid = substr($0, RSTART, RLENGTH)
      gsub(/^<div class="uid">[[:space:]]*|[[:space:]]*<\/div>$/, "", uid)
    }
    if (flag == 1 && match($0, /<div class="video-title">[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/div>/, m)) {
      flag = 2
      title = m[1]
    }
    if (flag == 2 && /<div class="meta">/) {
      flag = 3
    }
    if (flag == 3 && match($0, /(20[0-3][0-9])[\/._-](1[0-2]|0[1-9])[\/._-](3[01]|[12][0-9]|0[1-9])/, m)) {
      date = mktime(m[1] " " m[2] " " m[3] " 00 00 00")
      if (query_database_return(uid, title, date, "javdb.com")) {
        return 1
      }
    }
  }
  close(cmd)
  return 0
}

function modify_date_via_string(date)
{
  if (touch_file(date, "File name")) return 1
  return 0
}

function modify_file_via_database(date_strategy, rename_strategy, product_type, r)
{
  # date_strategy: query/local
  # rename_strategy: query/local
  # product_type: all/*

  tmp["match_regex"] = tolower(info["id"])
  gsub(/[_-]/, "[_-]?", tmp["match_regex"])

  r = javbus("uncensored/")
  if (! r) {
    if (product_type == "all") r = javbus()
    if (! r) r = javdb()
    if (! r) jav321()
  }

  if (tmp["title"] != "") {
    if (rename_strategy == "local") {
      rename_file(get_standard_product_id(file["basename"]), tmp["title"], tmp["source"])
    } else if (rename_strategy == "query") {
      rename_file(append_video_suffix(tmp["id"],info["id"]), tmp["title"], tmp["source"])
    }
  }

  if (date_strategy == "local") {
    if (touch_file(info["date"], "Product ID")) return 1
  } else if (date_strategy == "query") {
    if (touch_file(tmp["date"], tmp["source"])) return 1
  }
  return 0
}

function modify_time_via_exif(cmd)
{
  if (exiftool_installed) {
    cmd = ("exiftool -api largefilesupport=1 -Creat*Date -ModifyDate -Track*Date -Media*Date -Date*Original -d '%s' -S -s \"${target_file}\" 2>/dev/null")
    while ((cmd | getline) > 0) {
      if ($0 && $0 !~ /^0000/) {
        close(cmd)
        if (touch_file($0, "Exif")) {
          return 1
        }
      }
    }
    close(cmd)
  }
  return 0
}

function output(i,   divider_format,divider,final_date_display)
{
  if (i) {
    divider_format = "%s"
    divider = "------------------ SUCCESS --------------------"
  } else {
    divider_format = "\033[31m%s\033[0m"
    divider = "------------------ FAILED  --------------------"
  }
  final_date_display = (final["date"] ? strftime("%F %T", final["date"]) : "---")

  if (fifo != "") getline i < fifo
  else i = 1

  if (real_run) {
    if (final["title_changed"]) {
      printf("%s %s\n%15s: %s\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n",
        strftime("[%F %T]"), "Rename:",
        "Original path", file["fullpath"],
        "New name", final["filename"],
        "Title", final["title"],
        "Source", final["title_source"],
        divider_slim) >> logfile
    }
    if (final["date_changed"]) {
      printf("%s %s\n%15s: %s\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n",
        strftime("[%F %T]"), "Change Date:",
        "Path", (final["fullpath"] == "" ? file["fullpath"] : final["fullpath"]),
        "Original date", strftime("%F %T", file["date"]),
        "New date", final_date_display,
        "Source", final["date_source"],
        divider_slim) >> logfile
    }
  }
  printf(divider_format "\n%10s %s\n%10s %s\n%10s " (final["title_changed"] ? "\033[33m%s\033[0m" : "%s") "\n%10s " (final["date_changed"] ? "\033[33m%s\033[0m" : "%s") "\n%10s %s\n"),
    divider,
    "No:", i,
    "File:", (final["filename"] == "" ? file["filename"] : final["filename"]),
    "Title:", (final["title"] == "" ? "---" : final["title"]),
    "Date:", final_date_display,
    "Source:", (final["date_source"] == "" ? "---" : final["date_source"]) " / " (final["title_source"] == "" ? "---" : final["title_source"])

  if (fifo != "") {
    print(i + 1) > fifo
    close(fifo)
  }
}

function query_database_return(uid, title, date, source)
{
  if (uid != "" && title != "" && date) {
    tmp["id"] = uid
    tmp["title"] = title
    tmp["date"] = date
    tmp["source"] = source
    close(cmd)
    return 1
  }
  return 0
}

function rename_file(product_id, title, source,   filename,name_tmp,fullpath)
{
  if (product_id == "" || title == "") return 0
  filename = (product_id " " title)

  gsub(/[[:space:]<>:"/\|?* 　]/, " ", filename)
  gsub(/[[:space:]._-]{2,}/, " ", filename)
  gsub(/^[[:space:]._-]+|[[:space:]【\[（(.,_-]+$/, "", filename)

  while (bytes_length(filename file["ext"]) >= max_length) {
    name_tmp = gensub(/[[:space:]][^[:space:]]*$/, "", "1", filename)

    while (name_tmp == product_id) {
      sub(/.$/, "", filename)
      if (bytes_length(filename file["ext"]) < max_length) {
        name_tmp = 0
        break
      }
    }

    if (! name_tmp) break
    filename = name_tmp
  }
  filename = (filename file["ext"])

  if (filename != file["filename"]) {
    fullpath = (file["parentdir"] "/" filename)
    if (real_run) {
      ENVIRON["target_file_new"] = fullpath
      if (system("mv \"${target_file}\" \"${target_file_new}\"") == 0) {
        ENVIRON["target_file"] = fullpath
      } else {
        return 0
      }
    }
    final["title_changed"] = 1
    final["fullpath"] = fullpath
  }

  final["filename"] = filename
  final["title"] = title
  final["title_source"] = source
  return 1
}

function touch_file(date, source)
{
  if (! date) return 0

  if (date != file["date"]) {
    if (real_run) {

      if (system("touch -d '@" date "' \"${target_file}\"") != 0) {
        return 0
      }

    }
    final["date_changed"] = 1
  }

  final["date"] = date
  final["date_source"] = source
  return 1
}
