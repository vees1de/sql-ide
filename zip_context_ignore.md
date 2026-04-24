# Zip Context Ignore

This file is produced by a project scan from the global `zip-context` skill.

- The first block contains concrete exclusions detected in this project.
- The second block is for manual project-specific additions.
- Run `update` when the project layout changes and you want to rescan it.

## Auto-Detected Exclusions
<!-- zip-context:generated:start -->
```ignore
# Always exclude repository internals and local helper files
.git/
zip_context_ignore.md

# Found in this project: local metadata and editor noise
db-samples/spider_data/.DS_Store
*.swp
*.swo

# Found in this project: .gitignore and lockfiles
.gitignore
frontend/package-lock.json

# Found in this project: build, cache, and generated directories
.pytest_cache/
backend/.pytest_cache/
backend/.venv/
backend/app/__pycache__/
backend/app/agents/__pycache__/
backend/app/api/__pycache__/
backend/app/api/routes/__pycache__/
backend/app/core/__pycache__/
backend/app/db/__pycache__/
backend/app/evals/__pycache__/
backend/app/schemas/__pycache__/
backend/app/services/__pycache__/
backend/evals/__pycache__/
backend/scripts/__pycache__/
backend/test/__pycache__/
db-samples/__pycache__/
frontend/dist/
frontend/node_modules/
test/__pycache__/

# Detected binary/media/archive extensions in this project
*.ttf

# Found in this project: env or secret-like files
.env
frontend/.env
frontend/.env.remote.example
```
<!-- zip-context:generated:end -->

## Manual Additions
<!-- zip-context:extra:start -->
```ignore
# add project-specific patterns here
```
<!-- zip-context:extra:end -->
