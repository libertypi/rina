#!/usr/bin/env bash

LC_ALL=C.UTF-8 || LC_ALL=en_US.UTF-8
LANG=C.UTF-8 || LANG=en_US.UTF-8
export LC_ALL LANG

# Bash Version
((BASH_VERSINFO[0] >= 5 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 2))) || {
	printf '%s\n' "Error: The script requires at least bash 4.2 to run, exit."
	exit 1
}

# Awk Version
[[ $(awk -Wversion 2>&1 || awk --version 2>&1) != *'GNU Awk'* ]] && {
	printf '%s\n' "Error: The script requires GNU Awk to run, please make sure gawk is properly installed and configed as default."
	exit 1
}

declare -xr script_file="$(realpath "${BASH_SOURCE[0]}")"
declare -xr log_file="${script_file%/*}/log.log"
printf -v divider_bold '%0*s' "47" ""
declare -xr divider_bold="${divider_bold// /=}" divider_slim="${divider_bold// /-}"

handle_files() {

	get_standard_product_id() {
		awk '
		{
			org=$0
			$0=tolower($0); gsub(/[[:space:]\]\[)(}{._-]+/, " ", $0)
			for (i=1;i<=NF;i++) {
				if (!id) {
					if ($0 ~ /mesubuta/) {
						if ($i ~ /^[0-9][0-9][0-9][0-9][0-9][0-9]$/ && $(i+1) ~ /^[0-9][0-9][0-9]?[0-9]?[0-9]?$/ && $(i+2) ~ /^[0-9][0-9]?[0-9]?$/ ) {
							id= ( $i "_" $(i+1) "_" $(i+2) )
							$(i+1)=""
							$(i+2)=""
							flag=1; continue
						}
					}
					else if ($i ~ /^[0-9][0-9][0-9][0-9][0-9][0-9]$/ && $(i+1) ~ /^[0-9][0-9][0-9]?[0-9]?[0-9]?[0-9]?$/) {
						id=( $i "_" $(i+1) )
						$(i+1)=""
						flag=1; continue
					}
				}
				if (!studio) {
					if ($i ~ /^1pon(do)?$/) {
						studio="-1pon"
						flag=1; continue
					}
					else if ($i ~ /^10mu(sume)?$/) {
						studio="-10mu"
						flag=1; continue
					}
					else if ($i ~ /^carib(bean|com)*$/) {
						studio="-carib"
						flag=1; continue
					}
					else if ($i ~ /^carib(bean|com)*pr$/) {
						studio="-caribpr"
						flag=1; continue
					}
					else if ($i ~ /^mura(mura)?$/) {
						studio="-mura"
						flag=1; continue
					}
					else if ($i ~ /^paco(pacomama)?$/) {
						studio="-paco"
						flag=1; continue
					}
					else if ($i ~ /^mesubuta$/) {
						studio="-mesubuta"
						flag=1; continue
					}
				}
				if (flag && $i ~ /^((2160|1080|720|480)p|(high|mid|low|whole|f?hd|sd|psp)[0-9]*|[0-9])$/) other = ( other "-" $i )
				else if ($i != "") flag=0
			}
			if (id && studio) print id studio other
			else print org
		}'
	}

	rename_file() {
		if [[ $1 == "get_standard_product_id" ]]; then
			product_id="$(get_standard_product_id <<<"$file_basename")"
		else
			product_id="$1"
			[[ $file_basename =~ ${id//[-\/]/[^a-z0-9]?}[[:space:]_-](c|(2160|1080|720|480)p|(high|mid|low|whole|f?hd|sd|cd|psp)?[[:space:]_-]?[0-9]{1,2})([[:space:]_-]|$) ]] && product_id="${product_id}-${BASH_REMATCH[1]}"
		fi

		local name_tmp
		name_new="$(sed -E 's/[[:space:]<>:"/\|?* 　]/ /g;s/[[:space:]\._\-]{2,}/ /g;s/^[[:space:]\.\-]+|[[:space:]\.,\-]+$//g' <<<"${product_id} ${title}")"
		while (("$(wc -c <<<"${name_new}${file_ext}")" >= max_length)); do
			name_tmp="${name_new% *}"
			while [[ $name_tmp == "${product_id}" ]]; do
				name_new="${name_new:0:$((${#name_new} - 1))}"
				(("$(wc -c <<<"${name_new}${file_ext}")" < max_length)) && break 2
			done
			name_new="${name_tmp}"
		done
		name_new="${name_new}${file_ext}"

		if [[ ${name_new} != "${file_name}" ]]; then
			file_path="${target_file%/*}"
			file_new="${file_path}/${name_new}"
			name_old="${file_name}"
			if ((real_run)); then
				if mv "${target_file}" "${file_new}"; then
					printf "%(%F %T)T: Rename '%s' to '%s'. Source: %s.\n" "-1" "${file_path}/${name_old}" "${name_new}" "${title_source}" >>"${log_file}"
				else
					return
				fi
			fi
			target_file="${file_new}"
			title_changed=1
		fi
	}

	touch_file() {
		if ((date_org != date || title_changed)); then
			if ((real_run)); then
				if touch -d "@${date}" "${target_file}"; then
					printf "%(%F %T)T: Change Date: '%s' from '%(%F %T)T' to '%(%F %T)T'. Source: %s.\n" "-1" "${target_file}" "${date_org}" "${date}" "${date_source}" >>"${log_file}"
				else
					return 1
				fi
			fi
			date_changed=1
			return 0
		else
			return 0
		fi
	}

	modify_date_via_string() {
		date="$(date -d "$date" +%s)"
		if [[ -n $date ]]; then
			date_source="File name"
			touch_file && return 0
		fi
		return 1
	}

	modify_time_via_exif() {
		if ((exiftool_installed)); then
			date="$(exiftool -api largefilesupport=1 -Creat*Date -ModifyDate -Track*Date -Media*Date -Date*Original -d "%s" -S -s "${target_file}" 2>/dev/null | awk '$0 != "" && $0 !~ /^0000/ {print;exit}')"
			if [[ -n $date ]]; then
				date_source=Exif
				touch_file && return 0
			fi
		fi
		return 1
	}

	modify_file_via_database() {
		date_strategy="$1"   # 190230/query
		rename_strategy="$2" # local/query
		product_type="$3"    # all/uncensored

		match_regex="${id//-/[_-]?}"
		for i in "uncensored/" ""; do
			result="$(
				wget --tries=3 -qO- "https://www.javbus.com/${i}search/${id}" |
					awk -v regex="$match_regex" '
					BEGIN { regex=tolower(regex) }
					tolower($0) ~ ( "<a class=\"movie-box\" href=\"https://www\\.javbus\\.com/" regex "([^a-z0-9][^\"]*)?\">" ) {flag=1}
					flag == 1 && /<div class="photo-info">/ {flag=2}
					flag == 2 && match($0, /<span>.*<br/) {
						flag=3
						title = substr($0, RSTART, RLENGTH)
						gsub(/^<span>[[:space:]]*|[[:space:]]*<br$/, "", title)
					}
					flag == 3 && match(tolower($0), "<date>" regex "</date>") {
						flag=4
						uid = substr($0, RSTART, RLENGTH)
						gsub(/^<date>|<\/date>$/, "", uid)
					}
					flag == 4 && match($0, /20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) {
						date = substr($0, RSTART, RLENGTH); gsub(/[\.\/_]/, "-", date)
						if (uid && title && date) { printf "%s\n%s\n%s\n", uid, title, date ; exit }
					}'
			)"
			[[ $product_type == "uncensored" || -n $result ]] && break
		done
		if [[ -n $result ]]; then
			date_source=javbus.com
			title_source=javbus.com
		else
			result="$(
				wget --tries=3 -qO- "https://javdb.com/search?q=${id}&f=all" |
					awk -v regex="$match_regex" '
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
					flag == 3 && match($0, /20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) {
						date = substr($0, RSTART, RLENGTH); gsub(/[\.\/_]/, "-", date)
						if (uid && title && date) { printf "%s\n%s\n%s\n", uid, title, date ; exit }
					}'
			)"
			if [[ -n $result ]]; then
				date_source=javdb.com
				title_source=javdb.com
			else
				result="$(
					wget --tries=3 -qO- --post-data "sn=${id}" 'https://www.jav321.com/search' | awk '
						/<div class="panel-heading">/,// {
							if ( ! title && match($0, /<h3>[^<]+</) ) {
								title = substr($0, RSTART, RLENGTH)
								gsub(/^<h3>[[:space:]]*|[[:space:]]*<$/, "", title)
							}
							if ( ! uid && match($0, /<b>番号<\/b>[^<]+/) ) {
								uid = substr($0, RSTART, RLENGTH)
								gsub(/^<b>番号<\/b>[[:space:]:]*|[[:space:]]*$/, "", uid)
							}
							if ( ! date && match($0, /<b>发行日期<\/b>[[:space:]:]*20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) ) {
								date = substr($0, RSTART, RLENGTH)
								sub(/^<b>发行日期<\/b>[[:space:]:]*/, "", date) ; gsub(/[\.\/_]/, "-", date)
							}
							if (uid && title && date) { printf "%s\n%s\n%s\n", toupper(uid), title, date ; exit }
						}
					'
				)"
				if [[ -n $result ]]; then
					date_source=jav321.com
					title_source=jav321.com
				fi
			fi
		fi

		if [[ -n $result ]]; then
			uid="$(head -n1 <<<"$result")"
			title="$(sed -n '2p' <<<"$result")"
			case "$rename_strategy" in
			"local")
				rename_file "get_standard_product_id"
				;;
			"query")
				rename_file "${uid:-$id}"
				;;
			esac
		fi

		if [[ $date_strategy != "query" ]]; then
			date="$date_strategy"
			date_source="Product ID"
		elif [[ -n $result ]]; then
			date="$(sed -n '3p' <<<"$result")"
		fi
		if [[ -n $date ]] && date="$(date -d "$date" +%s)" && touch_file; then
			return 0
		else
			return 1
		fi
	}

	heydouga() {
		result="$(wget --tries=3 -qO- "${url}" | awk '
			! title && match($0, /<title>[^<]+<\/title>/) {
				title = substr($0, RSTART, RLENGTH)
				gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$|[[:space:]]*&#45;.*/, "", title)
			}
			! date && /配信日/ {
				do {
					if (match($0, /20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) ) {
						date = substr($0, RSTART, RLENGTH)
						gsub(/[\.\/_]/, "-", date)
						break
					}
				} while (getline > 0)
			}
			title && date { print title; print date ; exit }
		')"
		date="$(sed -n '2p' <<<"$result")"
		if [[ -n $date ]] && date="$(date -d "$date" +%s)"; then
			title="$(head -n1 <<<"$result")"
			if [[ -n $title ]]; then
				title_source='heydouga.com'
				rename_file "${name}-${id//\//-}"
			fi
			date_source='heydouga.com'
			touch_file && return 0
		fi
	}

	handle_videos() {
		file_basename="$(
			sed -E 's/.*/\L&\E/;
				s/(^\[[a-z0-9\.\-]+\.[a-z]{2,}\]|168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|tokyo[ _-]?hot|1000[ _-]?girl)[ _-]?//g
			' <<<"${file_name%.*}"
		)"
		regex_start='(^|[^a-z0-9])'
		regex_end='([^a-z0-9]|$)'

		# carib
		if [[ $file_basename =~ ${regex_start}carib(bean|pr|com)*${regex_end} && $file_basename =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			date="${id:4:2}${id:0:4}"
			if [[ -n $id ]]; then
				if [[ $file_basename =~ ${regex_start}carib(bean|com)*pr${regex_end} ]]; then
					url='https://www.caribbeancompr.com/moviepages'
					id="${id//-/_}"
				else
					url='https://www.caribbeancom.com/moviepages'
				fi
				title="$(wget --tries=3 -qO- "${url}/${id}/" | iconv -c -f EUC-JP -t UTF-8 | awk '
						/<div class="heading">/,/<\/div>/ {
							if ( match($0, /<h1[^>]*>[^<]+<\/h1>/) ) {
								title = substr($0, RSTART, RLENGTH)
								gsub(/^<h1[^>]*>[[:space:]]*|[[:space:]]*<\/h1>$/, "", title)
								print title ; exit
							}
						}
					')"
				if [[ -n $title ]]; then
					date="$(date -d "${date}" +%s)"
					date_source="Product ID"
					title_source='caribbeancom.com'
					rename_file "get_standard_product_id"
					touch_file && return 0
				else
					if modify_file_via_database "$date" "local" "uncensored"; then return 0; fi
				fi
			fi

		# 1pondo
		elif [[ $file_basename =~ ${regex_start}(1pon(do)?|10mu(sume)?|mura(mura)?|paco(pacomama)?)${regex_end} && $file_basename =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			date="${id:4:2}${id:0:4}"
			if [[ -n $id ]] && modify_file_via_database "$date" "local" "uncensored"; then return 0; fi

		# 160122_1020_01_Mesubuta
		elif [[ $file_basename =~ ${regex_start}mesubuta${regex_end} && $file_basename =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})[_-]([0-9]{2,4})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
			date="${id%%-*}"
			if [[ -n $id ]] && modify_file_via_database "$date" "local" "uncensored"; then return 0; fi

		# HEYZO-0988
		elif [[ $file_basename =~ ${regex_start}(heyzo|jukujo|kin8tengoku)[^0-9]*([0-9]{4})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			modify_file_via_database "query" "query" "uncensored" && return 0

		# honnamatv
		elif [[ $file_basename =~ ${regex_start}honnamatv[^0-9]*([0-9]{3,})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}"
			name=honnamatv
			url="https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/${id}/index.html"
			heydouga && return 0

		# heydouga-4197-001
		elif [[ $file_basename =~ ${regex_start}hey(douga)?[^a-z0-9]*([0-9]{4})[^a-z0-9]*([0-9]{3,})${regex_end} ]]; then
			id="${BASH_REMATCH[3]}/${BASH_REMATCH[4]}"
			name=heydouga
			url="https://www.heydouga.com/moviepages/${id}/index.html"
			heydouga && return 0

		# x1x-111815
		elif [[ $file_basename =~ ${regex_start}x1x[[:space:]_-]?([0-9]{6})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}"
			result="$(wget --tries=3 -qO- "http://www.x1x.com/title/${id}" | awk '
				! title && match($0, /<title>[^<]+<\/title>/) {
					title = substr($0, RSTART, RLENGTH)
					gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$/, "", title)
				}
				! date && /配信日/ {
					do {
						if (match($0, /20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) ) {
							date = substr($0, RSTART, RLENGTH); gsub(/[\.\/_]/, "-", date)
							break
						}
					} while (getline > 0)
				}
				title && date { print title; print date ; exit }
			')"
			date="$(sed -n '2p' <<<"$result")"
			if [[ -n $date ]] && date="$(date -d "$date" +%s)"; then
				title="$(head -n1 <<<"$result")"
				if [[ -n $title ]]; then
					title_source="x1x.com"
					rename_file "x1x-${id}"
				fi
				date_source="x1x.com"
				touch_file && return 0
			fi

		# h4610, c0930, h0930
		elif [[ $file_basename =~ ${regex_start}(h4610|[ch]0930)[^a-z0-9]+([a-z]+[0-9]+)${regex_end} ]]; then
			id="${BASH_REMATCH[2]^^}-${BASH_REMATCH[3]}"
			url="https://www.${id%-*}.com/moviepages/${id#*-}/"
			result="$(
				wget --tries=3 -qO- "${url}" | iconv -c -f EUC-JP -t UTF-8 | awk '
					! title && match($0, /<title>[^<]+<\/title>/) {
						title = substr($0, RSTART, RLENGTH)
						gsub(/^<title>[[:space:]]*|[[:space:]]*<\/title>$/, "", title)
					}
					! date && /dateCreated|startDate|uploadDate/ {
						do {
							if (match($0, /20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) ) {
								date = substr($0, RSTART, RLENGTH); gsub(/[\.\/_]/, "-", date)
								break
							}
						} while (getline > 0)
					}
					title && date { print title; print date ; exit }
				'
			)"
			date="$(sed -n '2p' <<<"$result")"
			if [[ -n $date ]] && date="$(date -d "$date" +%s)"; then
				title="$(head -n1 <<<"$result")"
				if [[ -n $title ]]; then
					title_source="${id%-*}.com"
					rename_file "${id}"
				fi
				date_source="${id%-*}.com"
				touch_file && return 0
			fi

		# FC2
		elif [[ $file_basename =~ ${regex_start}fc2[[:space:]_-]*(ppv)?[[:space:]_-]+([0-9]{2,10})${regex_end} ]]; then
			id="${BASH_REMATCH[3]}"
			result="$(
				wget --tries=3 -qO- "https://adult.contents.fc2.com/article/${id}/" | awk '
					! title && /<div class="items_article_headerInfo">/ && match($0, /<h3>[^<]+<\/h3>/) {
						title = substr($0, RSTART, RLENGTH)
						gsub(/^<h3>[[:space:]]*|[[:space:]]*<\/h3>$/, "", title)
					}
					! date && /<div class="items_article_Releasedate">/ && match($0, /<p>[^<:]*:[[:space:]]*20[0-3][0-9][\.\/_-](1[0-2]|0[1-9])[\.\/_-](3[01]|[12][0-9]|0[1-9])/) {
						date = substr($0, RSTART, RLENGTH)
						sub(/^<p>[^<:]*:[[:space:]]*/, "", date); gsub(/[\.\/_]/, "-", date)
					}
					title && date { print title; print date ; exit }'
			)"
			if [[ -z $result ]]; then
				result="$(
					wget --tries=3 -qO- "http://video.fc2.com/a/search/video/?keyword=${id}" | awk '
						match($0, /<a href="https:\/\/video.fc2.com\/a\/content\/[[:digit:]]+[^"]*" class="[^"]*" title="[^"]+" data-popd>[^<]+<\/a>/) {
						line = substr($0, RSTART, RLENGTH)
						title = gensub(/^[^>]*data-popd>[[:space:]]*|[[:space:]]*<\/a>/, "", "g", line)
						date = gensub(/^<a href="https:\/\/video.fc2.com\/a\/content\/([[:digit:]]+).*/, "\\1", "1", line)
						print title; print date ; exit
					}'
				)"
				if [[ -z $result ]]; then
					result="$(
						wget --tries=3 -qO- "https://fc2club.com/html/FC2-${id}.html" | awk '
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
									if (match($0,/<img class="responsive"[[:space:]]+src="\/uploadfile\/20[12][0-9]\/(1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])\//)) {
										date = gensub(/<img class="responsive"[[:space:]]+src="\/uploadfile\/(20[12][0-9])\/((1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9]))\//, "\\1\\2", "1", substr($0, RSTART, RLENGTH))
										break
									}
								} while (getline > 0)
							}
							title && date {print title; print date ; exit}
						'
					)"
				fi
			fi

			if [[ -n $result && -n ${date:=$(sed -n '2p' <<<"$result")} ]] && date="$(date -d "$date" +%s)"; then
				title="$(head -n1 <<<"$result")"
				if [[ -n $title ]]; then
					title_source="fc2.com"
					rename_file "FC2-${id}"
				fi
				date_source="fc2.com"
				touch_file && return 0
			fi

		# sm-miracle
		elif [[ $file_basename =~ ${regex_start}sm([[:space:]_-]miracle)?([[:space:]_-]no)?[[:space:]_\.\-]e?([0-9]{4})${regex_end} ]]; then
			id="e${BASH_REMATCH[4]}"
			date="$(wget --tries=3 -qO- "http://sm-miracle.com/movie3.php?num=${id}" | grep -Po -m1 '(?<=\/)20[12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9])(?=\/top)')"
			if [[ -n $date ]] && date="$(date -d "$date" +%s)"; then
				title="$(wget --tries=3 -qO- "http://sm-miracle.com/movie/${id}.dat" | sed -En "0,/^[[:space:][:punct:]]*title:[[:space:]\'\"]*([^\"\'\,]+[^[:space:]\"\'\,]).*/s//\1/p")"
				if [[ -n $title ]]; then
					title_source="sm-miracle.com"
					rename_file "sm-miracle-${id}"
				fi
				date_source="sm-miracle.com"
				touch_file && return 0
			fi

		# 1000girl
		elif [[ $file_basename =~ ${regex_start}([12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9]))[_-]?([a-z]{3,}(_[a-z]{3,})?)${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[5]}"
			modify_file_via_database "query" "query" "uncensored" && return 0

		# th101-000-123456
		elif [[ $file_basename =~ ${regex_start}(th101)[_-]([0-9]{3})[_-]([0-9]{6})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
			modify_file_via_database "query" "query" "uncensored" && return 0

		# mkbd_s24
		elif [[ $file_basename =~ ${regex_start}(mkbd|bd)[[:space:]_-]?([sm]?[0-9]+)${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			modify_file_via_database "query" "query" "uncensored" && return 0

		# tokyo hot
		elif [[ $file_basename =~ ${regex_start}((n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-3][0-9]{3}|(bouga|ka|sr|tr|sky)[0-9]{3,4})${regex_end} ]]; then
			[[ $file_basename =~ ${regex_start}(n|k|kb|jpgc|shiroutozanmai|hamesamurai|bouga|ka|sr|tr|sky)([0-9]{3,4})${regex_end} ]] && id="${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
			if [[ -n $id ]] && modify_file_via_database "query" "query" "uncensored"; then return 0; fi

		# club00379hhb
		elif [[ $file_basename =~ ${regex_start}([a-z]+)0{,2}([0-9]{3,4})hhb[0-9]?${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			modify_file_via_database "query" "query" "all" && return 0

		# MX-64
		elif [[ $file_basename =~ (^|\()([a-z]+(3d|3d2|2d|2m)*[a-z]+|xxx[_-]?av)[[:space:]_-]?([0-9]{2,6})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[4]}"
			modify_file_via_database "query" "query" "all" && return 0

		# 111111_111
		elif [[ $file_basename =~ ${regex_start}([0-9]{6})[_-]([0-9]{2,4})${regex_end} ]]; then
			id="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}"
			modify_file_via_database "query" "query" "uncensored" && return 0

		# 23.Jun.2014
		elif [[ $file_basename =~ ${regex_start}(3[01]|[12][0-9]|0?[1-9])[[:space:]\.\_\-]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[[:space:]\.\_\-]?(20[0-2][0-9])${regex_end} ]]; then
			date="${BASH_REMATCH[2]}-${BASH_REMATCH[3]}-${BASH_REMATCH[4]}"
			modify_date_via_string && return 0

		# (20)19.03.15
		elif [[ $file_basename =~ ${regex_start}((20)?(2[0-5]|1[0-9]|0[7-9]))[\._\-]?(1[0-2]|0[1-9])[\._\-]?(3[01]|[12][0-9]|0[1-9])${regex_end} ]]; then
			date="${BASH_REMATCH[2]}-${BASH_REMATCH[5]}-${BASH_REMATCH[6]}"
			modify_date_via_string && return 0

		# 23.02.20(19)
		elif [[ $file_basename =~ ${regex_start}(3[01]|[12][0-9]|0[1-9])[\._\-](1[0-2]|0[1-9])[\._\-]((20)?(2[0-5]|1[0-9]|0[7-9]))${regex_end} ]]; then
			date="${BASH_REMATCH[4]}-${BASH_REMATCH[3]}-${BASH_REMATCH[2]}"
			modify_date_via_string && return 0

		fi

		if modify_time_via_exif; then
			return 0
		else
			return 1
		fi
	}

	output() {
		[[ $title_changed == 1 ]] && title_format='\e[93m%s\e[0m'
		[[ $date_changed == 1 ]] && date_format='\e[93m%s\e[0m'
		[[ -n $date ]] && printf -v date "%(%F %T)T" "$date"
		flock -Fx "${script_file}" printf "%s\n%10s %s\n%10s ${title_format:-%s}\n%10s ${date_format:-%s}\n%10s %s\n" \
			"------------------ $1 --------------------" \
			"File:" "${name_new:-${file_name}}" \
			"Title:" "${title:----}" \
			"Date:" "${date:----}" \
			"Source:" "${date_source:----} / ${title_source:----}"
	}

	date_org="${1}"
	target_file="${2}"
	file_name="${target_file##*/}"                                                                       # Abc.MP4
	[[ ${file_name##*.} != "${file_name}" ]] && file_ext=".${file_name##*.}" && file_ext="${file_ext,,}" # .mp4

	case "$file_ext" in
	.3gp | .asf | .avi | .flv | .m2ts | .m2v | .m4p | .m4v | .mkv | .mov | .mp2 | .mp4 | .mpeg | .mpg | .mpv | .mts | .mxf | .rm | .rmvb | .ts | .vob | .webm | .wmv | .iso)
		if handle_videos; then
			output "Success"
		else
			output "Failed "
		fi
		;;
	*)
		if modify_time_via_exif; then
			output "Success"
		else
			output "Failed "
		fi
		;;
	esac
}

handle_dirs() {
	awk -v real_run="${real_run}" -v log_file="${log_file}" -v divider_slim="${divider_slim}" -v divider_bold="${divider_bold}" -v root_dir="${1}" '

	BEGIN {
		FS = "/"
		RS = "\000"
		count = 0
		success_count = 0
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
			while (($0 = substr($0, 1, length($0) - length(FS $NF))) && length($0) >= root_length) {
				if (file_date > dir[$0]) {
					dir[$0] = file_date
				}
			}
		} else if (dir[$0] && dir[$0] != file_date) {
			if (real_run) {
				if (system("touch -d \"@" dir[$0] "\" \"" $0 "\"") == 0) {
					printf("%s: Change Date: \"%s\" from \"%s\" to \"%s\".\n", strftime("%F %T"), $0, strftime("%F %T",file_date), strftime("%F %T",dir[$0])) >> log_file
				}
			}
			printf "\033[93m%7s   %-7s   %-10s   %s\033[0m\n", ++count, "Success", strftime("%F", dir[$0]), $NF
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
		if [[ $target_dir != "$new_dir" ]]; then
			color_start='\e[93m'
			color_end='\e[0m'
			if ((real_run)); then
				printf "%(%F %T)T: Rename: '%s' to '%s'. Source: %s.\n" "-1" "$target_dir" "$new_name" "$source" >>"${log_file}"
				mv "$target_dir" "$new_dir"
			fi
		fi
		printf "${color_start}%s ===> %s <=== %s${color_end}\n" "$actress_name" "${name}${birth}" "$source"
	}

	target_dir="${1}"
	actress_name="${target_dir##*/}"
	actress_name="${actress_name%([0-9][0-9][0-9][0-9]*}"
	[[ $actress_name == "$target_dir" || $actress_name =~ ^[A-Za-z0-9[:space:][:punct:]]*$ ]] && return

	# ja.wikipedia.org
	result="$(
		wget --tries=3 -qO- "https://ja.wikipedia.org/wiki/${actress_name}" |
			awk '
        !name && /<h1 id="firstHeading" class="firstHeading"[^>]*>[^<]+<\/h1>/{
            name = $0
            gsub(/^.*<h1 id="firstHeading" class="firstHeading"[^>]*>[[:space:]]*|[[:space:]]*<\/h1>.*$/, "", name)
        }
        /生年月日/{
        do
            {
                if ( ! birth && match($0, /title="[0-9][0-9][0-9][0-9]年">[0-9][0-9][0-9][0-9]年<\/a><a href="[^"]+" title="[0-9][0-9]?月[0-9][0-9]?日">[0-9][0-9]?月[0-9][0-9]?日<\/a>/) )
                {
                    date = substr($0, RSTART, RLENGTH)
                    y = gensub(/.*([0-9][0-9][0-9][0-9])年.*/, "\\1", 1, date)
                    m = sprintf("%02d", gensub(/.*[^0-9]([0-9][0-9]?)月.*/, "\\1", 1, date) )
                    d = sprintf("%02d", gensub(/.*[^0-9]([0-9][0-9]?)日.*/, "\\1", 1, date) )
					birth = ( y "-" m "-" d )
                }
                if ( $0 ~ /title="AV女優">AV女優<\/a>/ ) flag = 1
                if ( flag && birth )
                {
                    print name ; print birth
                    exit
                }
            }
        while ( getline > 0 )
        }'
	)"
	if [[ -n $result ]]; then
		source='ja.wikipedia.org'
		rename_actress_dir
		return
	fi

	# seesaawiki.jp
	result="$(wget --tries=3 -qO- "https://seesaawiki.jp/av_neme/search?keywords=$(iconv -c -f UTF-8 -t EUC-JP <<<"${actress_name}")" | iconv -c -f EUC-JP -t UTF-8 |
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
            if ( flag && match($0, /生年月日.*[0-9][0-9][0-9][0-9]年[[:space:]0-9]+月[[:space:]0-9]+日/ ) )
            {
                birth = substr($0, RSTART, RLENGTH)
                gsub(/^[^0-9]+|[[:space:]]+$/, "", birth)
                y = gensub(/([0-9][0-9][0-9][0-9])年.*/, "\\1", 1, birth)
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
		return
	fi

	# minnano-av.com
	minnano_av() {
		awk -v actress_name="${actress_name}" '
        /<h1>[^<]+<span>.*<\/span><\/h1>/ {
            gsub(/<span>[^<]*<\/span>/,"",$0)
            gsub(/^.*<h1>[[:space:]]*|[[:space:]]*<\/h1>.*$/, "", $0)
            name = $0
        }
        name && match($0, /生年月日.*[0-9][0-9][0-9][0-9]年[0-9][0-9]?月[0-9][0-9]?日/) {
            date = substr($0, RSTART, RLENGTH)
            y = gensub(/.*([0-9][0-9][0-9][0-9])年.*/, "\\1", 1, date)
            m = sprintf("%02d", gensub(/.*[^0-9]([0-9][0-9]?)月.*/, "\\1", 1, date) )
            d = sprintf("%02d", gensub(/.*[^0-9]([0-9][0-9]?)日/, "\\1", 1, date) )
            if ( y && m && d )
            {
                birth = ( y "-" m "-" d )
                print name ; print birth
                exit
            }
        }'
	}
	search="$(wget --tries=3 -qO- "http://www.minnano-av.com/search_result.php?search_scope=actress&search_word=${actress_name}")"
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
			result="$(wget --tries=3 -qO- "${i}" | minnano_av)"
			[[ -n $result ]] && break
		done
	else
		result="$(minnano_av <<<"$search")"
	fi
	if [[ -n $result ]]; then
		source='minnano-av.com'
		rename_actress_dir
		return
	fi

	# mankowomiseruavzyoyu.blog.fc2.com
	result="$(
		wget --tries=3 -qO- "http://mankowomiseruavzyoyu.blog.fc2.com/?q=${actress_name}" |
			awk -v actress_name="${actress_name}" '
            /dc:description="[^"]+"/ {
                gsub(/^[[:space:]]*dc:description="|"[[:space:]]*$|&[^;]*;/, " ", $0)
                name = $1
                gsub(/[[:space:] ]/,"",name)
                for (i=2; i<=NF; i++)
                {
                    if ( $i ~ "生年月日" && $(i+1) ~ /[0-9][0-9][0-9][0-9]年[0-9][0-9]?月[0-9][0-9]?日/ ) birth = $(i+1)
                    else if ( $i ~ "別名" ) alias = $(i+1)
                    if (birth && alias) break
                }
                y = gensub(/([0-9][0-9][0-9][0-9])年.*/, "\\1", 1, birth)
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
		return
	else
		printf "\e[31m%s ===> Failed.\e[0m\n" "$actress_name"
	fi
}

# Begin
printf '%s\n       %s\n                %s\n%s\n' "$divider_slim" "Adult Video Information Detector" "By David Pi" "$divider_slim"
help_info() {
	printf '%s\n' '
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
    -n, --thread      How many threads will be run at once. The default
                      number is 5 if not specified.
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
}
invalid_parameter() {
	printf '%s\n' "Invalid parameter: $1" "For more information, type: 'avinfo.sh --help'"
	exit
}
if [[ $# == "0" ]]; then
	help_info
	exit
else
	while (("$#")); do
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
		printf '\e[31m%s\e[0m\n%s\n' "Lack of target!" "For more information, type: 'avinfo.sh --help'"
		exit
	fi
fi
if [[ -z $real_run ]]; then
	printf '%s\n' "Please select a running mode." "In Test Run (safe) mode, changes will not be written into disk." "In Real Run mode, changes will be applied immediately." "It's recommend to try a test run first." ""
	PS3='Please enter your choice: '
	options=("Test Run" "Real Run" "Quit")
	select opt in "${options[@]}"; do
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
			exit
			;;
		*) printf '%s\n' "invalid option $REPLY" ;;
		esac
	done
fi
case "$real_run" in
0) printf '%s\n' "Test run mode selected, changes will NOT be written into disk." ;;
1) printf '%s\n' "Real run mode selected, changes WILL be written into disk." ;;
esac
declare -rx real_run

if command -v exiftool &>/dev/null; then
	declare -rx exiftool_installed=1
else
	printf '%s\n' "Lack dependency: Exiftool is not installed, will run without exif inspection."
	declare -rx exiftool_installed=0
fi
if ! command -v iconv &>/dev/null; then
	printf '%s\n' "Lack dependency: iconv is not installed, some site may not work properly!"
	exit
fi

if [[ -n $test_proxy ]]; then
	for i in $test_proxy; do
		if timeout 3 bash -c "</dev/tcp/${i/://}" &>/dev/null; then
			export http_proxy="http://${i}" https_proxy="http://${i}"
			printf '%s\n' "Using proxy: $i."
			break
		else
			printf '%s\n' "Unable to connect to proxy: $i."
		fi
	done
fi

# Filesystem Maximum Filename Length
if ! max_length="$(stat -f -c '%l' "${TARGET}")" || [[ -z ${max_length} || -n ${max_length//[0-9]/} ]]; then
	max_length=255
fi
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
		find "${TARGET}" -maxdepth 1 -mindepth 1 -type d -not -path "*/[@#.]*" -print0 | xargs -r -0 -n 1 -P "${thread}" bash -c 'handle_actress "$@"' _
		;;
	*)
		export -f handle_files
		find "${TARGET}" -type f -not -empty -not -path "*/[@#.]*" -printf '%Ts\0%p\0' | xargs -r -0 -n 2 -P "${thread}" bash -c 'handle_files "$@"' _
		printf '%s\n' "$divider_bold"
		handle_dirs "${TARGET}"
		;;
	esac
else
	handle_files "$(date -r "${TARGET}" +%s)" "${TARGET}"
fi
