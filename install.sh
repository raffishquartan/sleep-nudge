#!/usr/bin/env bash
#
# Configure and install the generate-sleep-nudges skill into your Claude Code
# skills directory. Substitutes per-user values into the skill template and
# writes the resolved files to a target directory (default: ~/.claude/skills/generate-sleep-nudges).
#
# Idempotent: re-running re-prompts using the values from the previous run as
# defaults, cached in ./.install-cache (gitignored).
#
# Usage:
#   ./install.sh                                # interactive, default target
#   ./install.sh --target /custom/skills/dir    # write to a different target
#   ./install.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/skills/generate-sleep-nudges"
CACHE_FILE="${SCRIPT_DIR}/.install-cache"
DEFAULT_TARGET="${HOME}/.claude/skills/generate-sleep-nudges"
TARGET=""

usage() {
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

TARGET="${TARGET:-${DEFAULT_TARGET}}"

if [[ ! -d "${TEMPLATE_DIR}" ]]; then
    echo "ERROR: template directory not found: ${TEMPLATE_DIR}" >&2
    echo "Run this script from the sleep-nudge repo root." >&2
    exit 1
fi

# Load cached values if present
declare -A DEFAULTS=(
    [REPO_ROOT]="${SCRIPT_DIR}"
    [ALLOWED_RECIPIENT]=""
    [ALLOWED_SENDER]=""
    [SUMMARY_SUBJECT_PREFIX]="Sleep Nudge generation summary "
    [NUDGE_SUBJECT_PREFIX]="Sleep Nudge - "
    [COMMIT_SUFFIX]=""
)

if [[ -f "${CACHE_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${CACHE_FILE}"
    for key in "${!DEFAULTS[@]}"; do
        cached_var="CACHED_${key}"
        if [[ -n "${!cached_var:-}" ]]; then
            DEFAULTS[$key]="${!cached_var}"
        fi
    done
fi

# Prompt for a value with a default. $1 = key, $2 = prompt description, $3 = required (yes/no)
prompt_for() {
    local key="$1" desc="$2" required="${3:-yes}" default="${DEFAULTS[$1]}" input
    while true; do
        if [[ -n "${default}" ]]; then
            read -r -p "${desc} [${default}]: " input
            input="${input:-${default}}"
        else
            read -r -p "${desc}: " input
        fi
        if [[ "${required}" == "yes" && -z "${input}" ]]; then
            echo "  (required - please enter a value)"
            continue
        fi
        echo "${input}"
        return 0
    done
}

validate_email() {
    local value="$1" label="$2"
    if [[ ! "${value}" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        echo "ERROR: ${label} is not a valid email address: ${value}" >&2
        exit 1
    fi
}

echo "=== generate-sleep-nudges install ==="
echo "Template:  ${TEMPLATE_DIR}"
echo "Target:    ${TARGET}"
echo
echo "Press Enter to accept the bracketed default, or type a new value."
echo

REPO_ROOT=$(prompt_for REPO_ROOT "Path to your local clone of the sleep-nudge repo")
ALLOWED_RECIPIENT=$(prompt_for ALLOWED_RECIPIENT "Recipient Gmail address (where the post-generation summary email goes)")
ALLOWED_SENDER=$(prompt_for ALLOWED_SENDER "Sender Gmail address (the account whose App Password the daily mailman uses)")
SUMMARY_SUBJECT_PREFIX=$(prompt_for SUMMARY_SUBJECT_PREFIX "Subject prefix for the generation summary email")
NUDGE_SUBJECT_PREFIX=$(prompt_for NUDGE_SUBJECT_PREFIX "Subject prefix for each daily nudge email")
COMMIT_SUFFIX=$(prompt_for COMMIT_SUFFIX "Trailing line for skill-generated git commit messages (optional, blank for none)" no)

validate_email "${ALLOWED_RECIPIENT}" "ALLOWED_RECIPIENT"
validate_email "${ALLOWED_SENDER}" "ALLOWED_SENDER"

if [[ ! -d "${REPO_ROOT}" ]]; then
    echo "ERROR: REPO_ROOT does not exist as a directory: ${REPO_ROOT}" >&2
    exit 1
fi

echo
echo "=== summary ==="
echo "REPO_ROOT              = ${REPO_ROOT}"
echo "ALLOWED_RECIPIENT      = ${ALLOWED_RECIPIENT}"
echo "ALLOWED_SENDER         = ${ALLOWED_SENDER}"
echo "SUMMARY_SUBJECT_PREFIX = ${SUMMARY_SUBJECT_PREFIX}"
echo "NUDGE_SUBJECT_PREFIX   = ${NUDGE_SUBJECT_PREFIX}"
echo "COMMIT_SUFFIX          = ${COMMIT_SUFFIX:-(none)}"
echo "TARGET                 = ${TARGET}"
echo
read -r -p "Proceed? [y/N] " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Substitute placeholders in each file under the template tree and write to the target.
export REPO_ROOT ALLOWED_RECIPIENT ALLOWED_SENDER SUMMARY_SUBJECT_PREFIX NUDGE_SUBJECT_PREFIX COMMIT_SUFFIX

mkdir -p "${TARGET}"

# shellcheck disable=SC2016
SUBSTITUTE='
import os, sys
keys = ["REPO_ROOT", "ALLOWED_RECIPIENT", "ALLOWED_SENDER",
        "SUMMARY_SUBJECT_PREFIX", "NUDGE_SUBJECT_PREFIX", "COMMIT_SUFFIX"]
data = sys.stdin.read()
for k in keys:
    data = data.replace("{{" + k + "}}", os.environ.get(k, ""))
sys.stdout.write(data)
'

while IFS= read -r -d '' src; do
    rel="${src#${TEMPLATE_DIR}/}"
    dst="${TARGET}/${rel}"
    mkdir -p "$(dirname "${dst}")"
    python3 -c "${SUBSTITUTE}" < "${src}" > "${dst}"
    # Preserve executable bit if set on source
    if [[ -x "${src}" ]]; then chmod +x "${dst}"; fi
done < <(find "${TEMPLATE_DIR}" -type f -print0)

# Write the cache for next run
{
    echo "# Cached values from the most recent install.sh run."
    echo "# Used to pre-fill the prompts when you re-run install.sh."
    echo "# Gitignored."
    for key in REPO_ROOT ALLOWED_RECIPIENT ALLOWED_SENDER SUMMARY_SUBJECT_PREFIX NUDGE_SUBJECT_PREFIX COMMIT_SUFFIX; do
        printf 'CACHED_%s=%q\n' "${key}" "${!key}"
    done
} > "${CACHE_FILE}"

echo
echo "Wrote skill to: ${TARGET}"
echo "Cached values for next run: ${CACHE_FILE}"
echo
echo "Next step: verify Claude Code can see the skill:"
echo "  ls ${TARGET}/SKILL.md"
echo "  cat ${TARGET}/SKILL.md | head -5"
echo
echo "If your skills directory is somewhere other than ~/.claude/skills/, run:"
echo "  ./install.sh --target /path/to/your/claude/skills/generate-sleep-nudges"
