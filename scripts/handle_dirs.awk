#!/usr/bin/awk -f

BEGIN {
  FS = OFS = "/"
  RS = "\000"
  real_run = (ENVIRON["real_run"] ? 1 : 0)
  divider_slim = ENVIRON["divider_slim"]
  divider_bold = ENVIRON["divider_bold"]
  logfile = ENVIRON["logfile"]
  root_length = length(target_root)

  count = success_count = 0
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
      if (system("touch -d '@" date[$0] "' \"${touch_dir}\"") == 0) {
        printf("[%s] %s\n%15s: %s\n%15s: %s\n%15s: %s\n%s\n",
          strftime("%F %T"), "Change Dir Date",
          "Path", $0,
          "Original date", strftime("%F %T",file_date),
          "New date", strftime("%F %T",date[$0]),
          divider_slim) >> logfile
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
