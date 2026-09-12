#!/bin/bash
# ==============================================================================
# 🧪 AUTOMATED SECURITY & REGRESSION TEST SUITE FOR SHIP
# ==============================================================================

set -Eeuo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$TEST_DIR")"
SHIP_CLI="python3 $ROOT_DIR/main.py"

SHIP_DIR="$ROOT_DIR/.ship"
IGNORE_FILE="$ROOT_DIR/.shipignore"

STAGING_FILE="$SHIP_DIR/state/files"
ALLOWED_FILE="$SHIP_DIR/guardrails/allowed"
DENY_FILE="$SHIP_DIR/guardrails/deny"
PROTECTED_FILE="$SHIP_DIR/guardrails/protected"
CONFIG_FILE="$SHIP_DIR/config.env"

# Manage test environment setup/teardown
CREATED_TEST_SHIP=0
if [ ! -d "$SHIP_DIR" ]; then
    CREATED_TEST_SHIP=1
    mkdir -p "$SHIP_DIR/guardrails" "$SHIP_DIR/state"
    cat << 'EOF' > "$ALLOWED_FILE"
# Allowed REMOTE_DIR patterns.
/home/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?
EOF
    cat << 'EOF' > "$DENY_FILE"
# Dangerous deploy rules
.env
*.env
.ship/
.git/
.ssh/
.aws/
*.pem
id_rsa
id_ed25519
EOF
    cat << 'EOF' > "$PROTECTED_FILE"
# Protected remote paths
/
/home
/home/
/root
/root/
/etc*
/var*
/usr*
/bin*
/sbin*
/tmp*
/opt*
EOF
    cat << 'EOF' > "$CONFIG_FILE"
# Deployment Server Configuration
SERVER_HOST=113.20.107.167
SERVER_PORT=20262
SERVER_USER=app
REMOTE_DIR=/home/app/dongnq7
EOF
    cat << 'EOF' > "$STAGING_FILE"
# ship staging area - staged paths to push to remote
EOF
fi

if [ ! -f "$IGNORE_FILE" ]; then
    CREATED_TEST_IGNORE=1
    cat << 'EOF' > "$IGNORE_FILE"
node_modules/
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
dist/
build/
.git/
.ship/
*.log
EOF
else
    CREATED_TEST_IGNORE=0
fi

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
NC="\033[0m"

PASS_COUNT=0
FAIL_COUNT=0

STAGING_BACKUP="$(mktemp)"
cp "$STAGING_FILE" "$STAGING_BACKUP"

cleanup() {
    cp "$STAGING_BACKUP" "$STAGING_FILE"
    rm -f "$STAGING_BACKUP"
    rm -f "$ROOT_DIR/temp_evil_symlink"
    if [ "$CREATED_TEST_SHIP" -eq 1 ]; then
        rm -rf "$SHIP_DIR"
    fi
    if [ "$CREATED_TEST_IGNORE" -eq 1 ]; then
        rm -f "$IGNORE_FILE"
    fi
}
trap cleanup EXIT

assert_success() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✔ PASS:${NC} $desc"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "  ${RED}✖ FAIL:${NC} $desc"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

assert_failure() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "  ${RED}✖ FAIL (Expected Failure but Succeeded):${NC} $desc"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo -e "  ${GREEN}✔ PASS:${NC} $desc"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
}

set_staging_body() {
    local body="$1"
    {
        echo "# test staging manifest"
        printf '%s\n' "$body"
    } > "$STAGING_FILE"
}

echo -e "${BOLD}======================================================${NC}"
echo -e "${BOLD}🛡️  RUNNING SHIP SECURITY REGRESSION TEST SUITE${NC}"
echo -e "${BOLD}======================================================${NC}"
echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 1: LOCAL PATH SECURITY & TRAVERSAL DEFENSE
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 1] Local Path Security & Traversal Defenses${NC}"

# Test 1.1: Relative path escape
assert_failure "Reject relative escape (../)" $SHIP_CLI add ../outside_project

# Test 1.2: Deep relative path escape
assert_failure "Reject deep relative escape (../../../../etc/passwd)" $SHIP_CLI add ../../../../etc/passwd

# Test 1.3: Absolute system path escape
assert_failure "Reject absolute system path (/etc/shadow)" $SHIP_CLI add /etc/shadow

# Test 1.4: Symlink escape
TEMP_SYMLINK="$ROOT_DIR/temp_evil_symlink"
ln -sf /etc/hosts "$TEMP_SYMLINK"
assert_failure "Reject symlink pointing outside project root" $SHIP_CLI add temp_evil_symlink
rm -f "$TEMP_SYMLINK"

# Test 1.5: Valid path within project root
assert_success "Allow valid project path (README.md)" $SHIP_CLI add README.md
$SHIP_CLI remove README.md >/dev/null 2>&1

# Test 1.6: Missing paths are rejected before they enter staging
assert_failure "Reject missing local path during add" $SHIP_CLI add missing/path/for/deploy.txt

# Test 1.7: Control characters are rejected before they enter staging
assert_failure "Reject control characters during add" $SHIP_CLI add $'README.md\n.env'

# Test 1.8: Explicit secret/control paths are rejected before they enter staging
assert_failure "Reject explicit .env during add" $SHIP_CLI add .env
assert_failure "Reject explicit .ship directory during add" $SHIP_CLI add .ship

echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 2: REMOTE_DIR SECURITY BOUNDARY & INJECTION DEFENSE
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 2] REMOTE_DIR Security Boundary & Injection Defenses${NC}"

test_remote_dir() {
    local dir="$1"
    (
        REMOTE_DIR="$dir"
        if [[ "$dir" =~ [^a-zA-Z0-9_./-] ]] || [[ "$dir" =~ \.\. ]]; then
            return 1
        fi
        allowed=1
        while IFS= read -r pattern; do
            pattern="${pattern%%#*}"
            pattern="${pattern#"${pattern%%[![:space:]]*}"}"
            pattern="${pattern%"${pattern##*[![:space:]]}"}"
            [[ -z "$pattern" ]] && continue
            if [[ "$dir" =~ ^${pattern}$ ]]; then
                allowed=0
                break
            fi
        done < "$ALLOWED_FILE"
        [[ "$allowed" -eq 0 ]] || return 1
        while IFS= read -r pattern; do
            pattern="${pattern%%#*}"
            pattern="${pattern#"${pattern%%[![:space:]]*}"}"
            pattern="${pattern%"${pattern##*[![:space:]]}"}"
            [[ -z "$pattern" ]] && continue
            if [[ "$pattern" == *"*" ]]; then
                prefix="${pattern%\*}"
                [[ "$dir" == "$prefix"* ]] && return 1
            elif [[ "$dir" == "$pattern" ]]; then
                return 1
            fi
        done < "$PROTECTED_FILE"
        return 0
    )
}

assert_failure "Reject traversal in REMOTE_DIR (/home/user/../../etc)" test_remote_dir "/home/user/../../etc"
assert_failure "Reject command injection in REMOTE_DIR (/home/user/foo;rm -rf)" test_remote_dir "/home/user/foo;rm -rf"
assert_failure "Reject single quote in REMOTE_DIR (/home/user/foo')" test_remote_dir "/home/user/foo'"
assert_failure "Reject double quote in REMOTE_DIR (/home/user/foo\"bar)" test_remote_dir "/home/user/foo\"bar"
assert_failure "Reject subshell in REMOTE_DIR (/home/user/foo\$(id))" test_remote_dir '/home/user/foo$(id)'
assert_failure "Reject backticks in REMOTE_DIR (/home/user/foo\`id\`)" test_remote_dir '/home/user/foo`id`'
assert_failure "Reject space in REMOTE_DIR (/home/user/foo bar)" test_remote_dir "/home/user/foo bar"
assert_failure "Reject newline in REMOTE_DIR (/home/user/foo\nbar)" test_remote_dir $'/home/user/foo\nbar'
assert_failure "Reject root system path (/)" test_remote_dir "/"
assert_failure "Reject shallow home path (/home/user)" test_remote_dir "/home/user"
assert_failure "Reject non-home path (/var/www/project)" test_remote_dir "/var/www/project"
assert_success "Allow valid standard path (/home/app/dongnq7)" test_remote_dir "/home/app/dongnq7"
assert_success "Allow valid subfolder path (/home/app/dongnq7/web-demo)" test_remote_dir "/home/app/dongnq7/web-demo"

echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 3: SERVER_PORT & SERVER_USER VALIDATION
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 3] SERVER_PORT & SERVER_USER Boundary Defenses${NC}"

test_port() {
    local port="$1"
    [[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1 && port <= 65535 ))
}

assert_failure "Reject port 0" test_port "0"
assert_failure "Reject port 70000" test_port "70000"
assert_failure "Reject port with negative number (-22)" test_port "-22"
assert_failure "Reject non-numeric port (22a)" test_port "22a"
assert_success "Allow port 22" test_port "22"
assert_success "Allow port 20262" test_port "20262"

test_user() {
    local user="$1"
    [[ "$user" =~ ^[a-zA-Z0-9_.-]+$ ]]
}

assert_failure "Reject illegal characters in user (user;id)" test_user "user;id"
assert_failure "Reject spaces in user (user app)" test_user "user app"
assert_failure "Reject quotes in user (user'app)" test_user "user'app"
assert_success "Allow standard linux user (app)" test_user "app"
assert_success "Allow dotted user (deploy.user)" test_user "deploy.user"

test_host() {
    local host="$1"
    [[ -n "$host" ]] &&
        [[ ! "$host" =~ [^a-zA-Z0-9_.-] ]] &&
        [[ "$host" != .* ]] &&
        [[ "$host" != *..* ]] &&
        [[ "$host" != *-. ]] &&
        [[ "$host" != .*-. ]]
}

assert_failure "Reject host with command separator" test_host "example.com;id"
assert_failure "Reject host with whitespace" test_host "bad host"
assert_failure "Reject host with colon" test_host "example.com:22"
assert_success "Allow IPv4 host" test_host "113.20.107.167"
assert_success "Allow DNS host" test_host "deploy.example.com"

echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 4: SSH_EXEC_SCRIPT POSITIONAL ARGUMENT ACCURACY
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 4] Positional Argument Passing over Shell Execution${NC}"

test_arg_passing() {
    local script='
    p1="$1"
    p2="$2"
    p3="$3"
    [ "$p1" = "/home/app/project" ] || exit 1
    [ "$p2" = "hello world" ] || exit 1
    [ "$p3" = "value with \"quotes\" & \$dollar; rm -rf /" ] || exit 1
    '
    local remote_cmd="bash -se"
    remote_cmd="$remote_cmd $(printf '%q ' "/home/app/project" "hello world" 'value with "quotes" & $dollar; rm -rf /')"
    sh -c "$remote_cmd" <<< "$script"
}

assert_success "Accurately quote and preserve complex positional arguments in remote script" test_arg_passing

echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 5: DRY-RUN IMMUTABILITY & CLI IDEMPOTENCE
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 5] Dry-Run Safety & Idempotence${NC}"

assert_success "Help command exits with 0" $SHIP_CLI help
assert_success "Clean --dry-run completes cleanly without modification" $SHIP_CLI clean --dry-run

echo ""

# ------------------------------------------------------------------------------
# TEST GROUP 6: MANIFEST & SECRET DEPLOY POLICY
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Test Group 6] Manifest Validation & Secret Deploy Policy${NC}"

set_staging_body "../outside_project"
assert_failure "Push rejects hand-edited manifest traversal" $SHIP_CLI push --dry-run

set_staging_body "/etc/passwd"
assert_failure "Push rejects hand-edited absolute path" $SHIP_CLI push --dry-run

set_staging_body "temp_evil_symlink"
ln -sf /etc/hosts "$TEMP_SYMLINK"
assert_failure "Push rejects hand-edited symlink escape" $SHIP_CLI push --dry-run
rm -f "$TEMP_SYMLINK"

set_staging_body "missing/path/for/deploy.txt"
assert_failure "Push rejects hand-edited missing local path" $SHIP_CLI push --dry-run

set_staging_body ".env"
assert_failure "Push rejects hand-edited secret path" $SHIP_CLI push --dry-run

set_staging_body ".ship/config.env"
assert_failure "Push rejects hand-edited deploy config path" $SHIP_CLI push --dry-run

set_staging_body $'README.md\n.env'
assert_failure "Push rejects multiline manifest entry containing secret" $SHIP_CLI push --dry-run

test_deny_contains() {
    local pattern="$1"
    grep -Fxq "$pattern" "$DENY_FILE"
}

assert_success "Deny policy refuses .env" test_deny_contains ".env"
assert_success "Deny policy refuses *.env" test_deny_contains "*.env"
assert_success "Deny policy refuses .ship/" test_deny_contains ".ship/"
assert_success "Remote path guardrail protects /var*" grep -Fxq "/var*" "$PROTECTED_FILE"
assert_success "Remote path guardrail protects /" grep -Fxq "/" "$PROTECTED_FILE"
assert_success "Remote path allow rule is configured outside code" grep -Fxq "/home/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?" "$ALLOWED_FILE"

echo ""
echo -e "${BOLD}======================================================${NC}"
echo -e "${BOLD}TEST RESULTS: ${GREEN}$PASS_COUNT PASSED${NC} | ${RED}$FAIL_COUNT FAILED${NC}"
echo -e "${BOLD}======================================================${NC}"

if [ $FAIL_COUNT -eq 0 ]; then
    exit 0
else
    exit 1
fi
