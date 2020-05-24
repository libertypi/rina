#!/usr/bin/awk -f

BEGIN {

  if ((real_run = ENVIRON["real_run"]) == "" ||
    (divider_slim = ENVIRON["divider_slim"]) == "" ||
    (logfile = ENVIRON["logfile"]) == "") {
    print("Please do not run this Awk script directly, use avinfo.bash.") > "/dev/stderr"
    exit 1
  }

  target_dir = ARGV[1]
  dir_name = gensub(/.*\//, "", "1", target_dir)
  actress_name = gensub(/\([0-9]{4}.*|['"]/, "", "g", dir_name)
  if (dir_name == target_dir || actress_name ~ /^[A-Za-z0-9[:space:][:punct:]]*$/) exit

  wikipedia(actress_name)
  minnano_av(actress_name)
  seesaawiki(actress_name)
  mankowomiseruavzyoyu(actress_name)

  printf "\033[31m%s: %s\033[0m\n", "Failed", dir_name
}

function rename_and_quit(name, birth, source) {
  gsub(/[[:space:] ]|\([^\)]*\)|【[^】]*】|（[^）]*）/, "", name)
  new_name = name "(" birth ")"
  new_dir = gensub(/\/[^/]+$/, "", "1", target_dir) "/" new_name

  if (target_dir != new_dir) {
    color_start = "\033[93m"
    color_end = "\033[0m"
    if (real_run) {
      ENVIRON["target_dir"] = target_dir
      ENVIRON["new_dir"] = new_dir
      if (system("mv \"${target_dir}\" \"${new_dir}\"") == 0) {
        printf ("%s: %s\n%10s: %s\n%10s: %s\n%10s: %s\n%s\n",
          strftime("[%F %T]"), "Rename Directory",
          "From", target_dir,
          "To", new_name,
          "Source", source,
          divider_slim) >> logfile
      }
    }
  }
  printf (color_start "%s  ===>  %s  ===>  %s\n" color_end), source, dir_name, new_name
  exit
}

function escape(string) {
  return gensub(/[\]\[)(}{.]/, "\\\\&", "g", string)
}

function utf2jp(string, option,   cmd, s) {
  cmd = "iconv -c -f UTF-8 -t EUC-JP"
  print string |& cmd
  close(cmd, "to")
  cmd |& getline s
  close(cmd)
  return s
}

function wikipedia(actress_name,   m, cmd, flag1, flag2, name, birth) {
  cmd = ("wget -qO- 'https://ja.wikipedia.org/wiki/" actress_name "'")
  while ((cmd | getline) > 0) {
    if (name == "" && match($0, /<h1 id="firstHeading" class="firstHeading"[^>]*>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/h1>/, m)) {
      name = m[1]
    }
    if ($0 ~ /生年月日/) flag1 = 1
    if (flag1 && birth == "" && match($0, /title="[0-9]{4}年">([0-9]{4})年<\/a>.*title="[0-9]{1,2}月[0-9]{1,2}日">([0-9]{1,2})月([0-9]{1,2})日<\/a>/, m)) {
      birth = (m[1] "-" sprintf("%02d", m[2]) "-" sprintf("%02d", m[3]))
    }
    if ($0 ~ /title="AV女優">AV女優<\/a>/) flag2 = 1
    if (flag2 && name != "" && birth != "") {
      close(cmd)
      rename_and_quit(name, birth, "ja.wikipedia.org")
    }
  }
  close(cmd)
}

function minnano_av(actress_name, url,   escape_name, domain, cmd, m, name, birth) {
  escape_name = escape(actress_name)
  domain = "www.minnano-av.com/"
  if (url == "") {
    cmd = "wget -qO- '" domain "search_result.php?search_scope=actress&search_word=" actress_name "'"
  } else {
    cmd = "wget -qO- '" url "'"
  }
  while ((cmd | getline) > 0) {
    if ($0 ~ /<title>/) {
      do {
        if ($0 ~ /AV女優の検索結果/) {
          # Search for redirect url
          do {
            if ($0 ~ /<table[^>]*class="tbllist actress">/) {
              do {
                if (match($0, "<h2[^>]*><a href=\042([^>\042']+)\042>" escape_name "[^<]*</a></h2>", m) ) {
                  close(cmd)
                  minnano_av(actress_name, (m[1] ~ /^https?:\/\// ? m[1] : domain m[1]))
                  return
                }
              } while ((cmd | getline) > 0)
            }
          } while ((cmd | getline) > 0)
        }
        if ($0 ~ /<\/title>/) break
      } while ((cmd | getline) > 0)
    }
    if (match($0, /<h1>[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<span>[^<]+<\/span><\/h1>/, m)) {
      name = m[1]
    }
    if (name != "" && match($0, /生年月日.*([0-9]{4})年[[:space:]]*([0-9]{1,2})月[[:space:]]*([0-9]{1,2})日/, m)) {
      birth = (m[1] "-" sprintf("%02d", m[2]) "-" sprintf("%02d", m[3]))
    }
    if (name != "" && birth != "") {
      close(cmd)
      rename_and_quit(name, birth, "minnano-av.com")
    }
  }
  close(cmd)
}

function seesaawiki(actress_name,   cmd, matched, m, name, birth, i) {
  cmd = "wget -qO- 'https://seesaawiki.jp/av_neme/search?keywords=" utf2jp(actress_name) "' | iconv -c -f EUC-JP -t UTF-8"
  while ((cmd | getline) > 0) {
    if ($0 ~ /<div class="body">/) {
      do {
        if ( match($0, /<h3 class="keyword"><a href="[^"]+">[[:space:]]*([^<]*[^[:space:]<])[[:space:]]*<\/a><\/h3>/, m) ) {
          name = m[1]
          if (name == actress_name) matched = 1
        }
        if (! matched && $0 ~ /旧名義|別名|名前\(女優名\)/) {
          gsub(/<[^>]*>/, "", $0)
          gsub(/[\]\[}{}'"：【】)(）（・／\/]+|&[^;]*;/, " ", $0)
          for (i=1; i<=NF; i++) {
            if ($i == actress_name) {
              matched = 1
              break
            }
          }
        }
        if (match($0, /生年月日.*([0-9]{4})年[[:space:]]*([0-9]{1,2})月[[:space:]]*([0-9]{1,2})日/, m)) {
          birth = (m[1] "-" sprintf("%02d", m[2]) "-" sprintf("%02d", m[3]))
        }
        if (matched && name != "" && birth != "") {
          close(cmd)
          rename_and_quit(name, birth, "seesaawiki.jp")
        }
      } while ($0 !~ /<\/div><!-- \/body -->/ && (cmd | getline) > 0)
      name = birth = matched = ""
    }
  }
  close(cmd)
}

function mankowomiseruavzyoyu(actress_name,   escape_name, flag, cmd, m, i, name, birth) {
  cmd = "wget -qO- 'mankowomiseruavzyoyu.blog.fc2.com/?q=" actress_name "'"
  escape_name = escape(actress_name)
  while ((cmd | getline) > 0) {
    if ($0 ~ escape_name && match($0, /^[[:space:]]*dc:description="([^[:space:]&]+)/, m)) {
      name = m[1]
      birth = ""
      gsub(/["']|&[^;]*;/, " ", $0)
      for (i = 2; i <= NF; i++) {
        if ($i ~ "生年月日") flag = 1
        if (flag && match($i, /([0-9]{4})年[[:space:]]*([0-9]{1,2})月[[:space:]]*([0-9]{1,2})日/, m)) {
          birth = (m[1] "-" sprintf("%02d", m[2]) "-" sprintf("%02d", m[3]))
          break
        }
      }
      if (name != "" && birth != "") {
        close(cmd)
        rename_and_quit(name, birth, "mankowomiseruavzyoyu.blog.fc2.com")
      }
    }
  }
  close(cmd)
}
