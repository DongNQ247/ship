"""Default templates used when initializing a new .ship workspace."""

DEFAULT_ALLOWED = """# Allowed REMOTE_DIR patterns.
# Lines are regular expressions matched against the whole path.

/home/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?
"""

DEFAULT_DENY = """# ==============================================================================
# Dangerous deploy rules
# ==============================================================================
# These paths are refused by ship even if they are not listed in .shipignore.

.env
*.env
.ship/
.git/
.ssh/
.aws/
*.pem
id_rsa
id_ed25519
"""

DEFAULT_PROTECTED = """# ==============================================================================
# Protected remote paths
# ==============================================================================
# These remote paths must not be used as REMOTE_DIR for clean/deploy.

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
"""

DEFAULT_STAGING = """# ship staging area - staged paths to push to remote
# Add paths with:
#   ship add <path...>
#   ship add .
"""

DEFAULT_SHIPIGNORE = """# ==============================================================================
# .shipignore - Files and directories excluded from ship staging / sync
# ==============================================================================

# Node / Dependencies & cache
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Python virtual environment & cache
.venv/
venv/
env/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/

# Build artifacts
dist/
build/
.cache/

# Version Control & IDE files
.git/
.gitignore
.vscode/
.idea/
*.swp
*.swo

# Temporary & Log files
*.log
scratch/
brain/
"""
