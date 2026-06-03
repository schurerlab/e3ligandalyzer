#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-$PWD}"
cd "$BASE_DIR"

CONFLICT_DIR="_CONFLICTS"

for req in XIAP cIAP1 cIAP2; do
  [[ -d "$req" ]] || { echo "ERROR: missing directory '$req' in $BASE_DIR" >&2; exit 1; }
done

SOURCE_DIRS=(XIAP cIAP1 cIAP2)
ALL_DIRS=(XIAP cIAP1 cIAP2 LIVIN MIXED)

for d in "${ALL_DIRS[@]}"; do
  mkdir -p "$d/PDB" "$d/SDF" "$d/SDF_4Download"
done
mkdir -p "$CONFLICT_DIR"

# -----------------------------
# Final folder assignments
# -----------------------------

XIAP_IDS=(
  1TFQ_998 1TFT_997 2JK7_BI6 2OPY_CO9 3CLX_X22 3CM2_X23 3CM7_X22 3EYL_SMK
  3HL5_9JZ 4HY0_1AQ 4KJU_1RH 4KJV_1RK 4WVS_4LZ 4WVU_3V8 4WVU_HOX 5C0K_4WK
  5C0L_4WJ 5C3H_4XE 5C3K_4XF 5C7A_4YE 5C7B_4YD 5C7C_4YC 5C7D_4YF 5C83_4YN
  5C84_4YL 5M6E_7HT 5M6F_7HU 5M6H_7J6 5M6L_7H9 5M6M_7H8 5OQW_A4E 6EY2_C3T
  6H6Q_FUK 6H6R_FUE 8GH7_7PE 8GH7_CHG 8GH7_ZHW
)

CIAP1_IDS=(
  3MUP_SMK 3OZ1_BMB 4HY4_1BG 4HY5_1AQ 4LGE_1Y0 4LGU_1YH 4MTI_2DX 4MU7_2DY
  5M6N_7H9 6EXW_C3K 7TRM_IUN
)

LIVIN_IDS=(
  2I3I_618 3F7H_419 3F7I_G13 3GT9_516 3GTA_851
)

MIXED_IDS=(
  3UW4_0DQ 3UW4_CHG 3UW5_0DQ 3UW5_CHG
)

declare -A ID_DEST
declare -A TOKEN_DESTS

register_ids() {
  local dest="$1"
  shift
  local id token
  for id in "$@"; do
    ID_DEST["$id"]="$dest"
    token="${id##*_}"
    case " ${TOKEN_DESTS[$token]:-} " in
      *" $dest "*) ;;
      *)
        TOKEN_DESTS["$token"]="${TOKEN_DESTS[$token]:-} $dest"
        TOKEN_DESTS["$token"]="${TOKEN_DESTS[$token]# }"
        ;;
    esac
  done
}

register_ids "XIAP"  "${XIAP_IDS[@]}"
register_ids "cIAP1" "${CIAP1_IDS[@]}"
register_ids "LIVIN" "${LIVIN_IDS[@]}"
register_ids "MIXED" "${MIXED_IDS[@]}"

ALL_IDS=( "${XIAP_IDS[@]}" "${CIAP1_IDS[@]}" "${LIVIN_IDS[@]}" "${MIXED_IDS[@]}" )

log() {
  printf '%s\n' "$*"
}

same_file() {
  cmp -s -- "$1" "$2"
}

quarantine_file() {
  local src="$1"
  local rel_src dest_q
  rel_src="${src#./}"
  dest_q="$CONFLICT_DIR/$rel_src"
  mkdir -p "$(dirname "$dest_q")"

  if [[ -e "$dest_q" ]]; then
    local base ext n candidate
    base="${dest_q%.*}"
    ext=""
    [[ "$dest_q" == *.* ]] && ext=".${dest_q##*.}"
    if [[ "$ext" != "" ]]; then
      base="${dest_q%$ext}"
    fi
    n=1
    candidate="${base}.conflict${n}${ext}"
    while [[ -e "$candidate" ]]; do
      ((n++))
      candidate="${base}.conflict${n}${ext}"
    done
    dest_q="$candidate"
  fi

  log "QUARANTINE CONFLICT: $src -> $dest_q"
  mv -- "$src" "$dest_q"
}

move_or_delete() {
  local src="$1"
  local dest="$2"

  [[ -e "$src" ]] || return 0

  if [[ "$src" == "$dest" ]]; then
    return 0
  fi

  mkdir -p "$(dirname "$dest")"

  if [[ -e "$dest" ]]; then
    if same_file "$src" "$dest"; then
      log "REMOVE DUPLICATE: $src"
      rm -f -- "$src"
    else
      quarantine_file "$src"
    fi
  else
    log "MOVE: $src -> $dest"
    mv -- "$src" "$dest"
  fi
}

process_id_bundle() {
  local src_dir="$1"
  local id="$2"
  local dest_dir="${ID_DEST[$id]}"

  move_or_delete "$src_dir/PDB/$id.pdb" "$dest_dir/PDB/$id.pdb"
  move_or_delete "$src_dir/SDF_4Download/$id.sdf" "$dest_dir/SDF_4Download/$id.sdf"
}

find_token_template() {
  local token="$1"
  local first=""
  local candidate
  local dirs=(XIAP cIAP1 cIAP2 LIVIN MIXED)

  for d in "${dirs[@]}"; do
    candidate="$d/SDF/${d}_${token}.sdf"
    if [[ -e "$candidate" ]]; then
      if [[ -z "$first" ]]; then
        first="$candidate"
      else
        if ! same_file "$candidate" "$first"; then
          log "TOKEN TEMPLATE MISMATCH for token '$token':"
          log "  keeping template: $first"
          quarantine_file "$candidate"
        fi
      fi
    fi
  done

  [[ -n "$first" ]] && printf '%s\n' "$first"
}

ensure_token_copies() {
  local token="$1"
  local required="${TOKEN_DESTS[$token]:-}"
  local template
  local dest
  local dest_file
  local src
  local src_file

  template="$(find_token_template "$token" || true)"

  if [[ -z "$template" ]]; then
    log "WARNING: no token-SDF found for token '$token'; skipping token-SDF creation"
    return 0
  fi

  for dest in $required; do
    dest_file="$dest/SDF/${dest}_${token}.sdf"
    if [[ -e "$dest_file" ]]; then
      if ! same_file "$dest_file" "$template"; then
        quarantine_file "$dest_file"
        log "COPY: $template -> $dest_file"
        cp -p -- "$template" "$dest_file"
      fi
    else
      if [[ "$template" != "$dest_file" ]]; then
        log "COPY: $template -> $dest_file"
        cp -p -- "$template" "$dest_file"
      fi
    fi
  done

  for src in "${SOURCE_DIRS[@]}"; do
    src_file="$src/SDF/${src}_${token}.sdf"
    [[ -e "$src_file" ]] || continue

    case " $required " in
      *" $src "*) ;;
      *)
        log "REMOVE EXTRA TOKEN-SDF: $src_file"
        rm -f -- "$src_file"
        ;;
    esac
  done
}

# -----------------------------
# Move PDB + SDF_4Download files
# -----------------------------
for src in "${SOURCE_DIRS[@]}"; do
  for id in "${ALL_IDS[@]}"; do
    process_id_bundle "$src" "$id"
  done
done

# -----------------------------
# Fix token-based SDF files
# -----------------------------
declare -A SEEN_TOKEN
for id in "${ALL_IDS[@]}"; do
  token="${id##*_}"
  if [[ -z "${SEEN_TOKEN[$token]:-}" ]]; then
    ensure_token_copies "$token"
    SEEN_TOKEN["$token"]=1
  fi
done

echo
echo "=== FINAL CHECK ==="
for d in XIAP cIAP1 cIAP2 LIVIN MIXED; do
  pdb_count=$(find "$d/PDB" -maxdepth 1 -type f -name '*.pdb' 2>/dev/null | wc -l | tr -d ' ')
  sdf_count=$(find "$d/SDF" -maxdepth 1 -type f -name '*.sdf' 2>/dev/null | wc -l | tr -d ' ')
  dl_count=$(find "$d/SDF_4Download" -maxdepth 1 -type f -name '*.sdf' 2>/dev/null | wc -l | tr -d ' ')
  printf '%-6s  PDB=%-3s  SDF=%-3s  SDF_4Download=%-3s\n' "$d" "$pdb_count" "$sdf_count" "$dl_count"
done

echo
if find cIAP2/PDB cIAP2/SDF cIAP2/SDF_4Download -type f 2>/dev/null | grep -q .; then
  echo "WARNING: cIAP2 is not completely empty. Leftover files:"
  find cIAP2/PDB cIAP2/SDF cIAP2/SDF_4Download -type f | sort
else
  echo "cIAP2 is empty."
fi

echo
echo "Conflict files, if any, were moved into: $CONFLICT_DIR"