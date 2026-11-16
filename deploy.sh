#!/usr/bin/env bash
# Deploy the English micro-tool to GitHub Pages.
#   bash deploy.sh
# Idempotent: safe to run again after a partial failure.
set -u
OWNER="gkdlwjavm9-cpu"
REPO="protein-cost-calculator-en"
BRANCH="main"
URL="https://${OWNER}.github.io/${REPO}/"
cd "$(dirname "$0")" || exit 1

echo "== 1. repository $OWNER/$REPO"
if gh api "repos/$OWNER/$REPO" >/dev/null 2>&1; then
  echo "   already exists"
else
  echo "   creating…"
  if ! gh api -X POST user/repos -f name="$REPO" \
        -f description="Free protein cost per gram and daily target calculator" \
        -F homepage="$URL" -F private=false >/dev/null 2>&1; then
    cat <<'EOS'
   !! The GitHub connection has no permission to create repositories
      (403 "Resource not accessible by integration"), so this needs 30 seconds of
      the account owner's time:

        1. Open https://github.com/new
        2. Repository name: protein-cost-calculator-en
        3. Visibility: Public. Leave "Add a README file" unticked.
        4. Create repository

      If the Pickle GitHub app is limited to selected repositories, also add the new
      repo at https://github.com/apps/pickle/installations/new

      Then run this script again.
EOS
    exit 2
  fi
fi

echo "== 2. commit"
if [ ! -d .git ]; then git init -q -b "$BRANCH" 2>/dev/null || git init -q; fi
git add -A
git -c user.name="$OWNER" -c user.email="${OWNER}@users.noreply.github.com" \
    commit -q -m "Protein cost per gram & daily target calculator (English, single file)" \
    || echo "   nothing new to commit"
git branch -M "$BRANCH" 2>/dev/null
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"

echo "== 3. push"
git push -u origin "$BRANCH" || { echo "   !! push failed"; exit 3; }

echo "== 4. GitHub Pages"
if gh api "repos/$OWNER/$REPO/pages" >/dev/null 2>&1; then
  echo "   Pages already enabled"
else
  gh api -X POST "repos/$OWNER/$REPO/pages" \
     -f "source[branch]=$BRANCH" -f "source[path]=/" >/dev/null \
     || echo "   !! could not enable Pages through the API — enable it at https://github.com/$OWNER/$REPO/settings/pages"
fi

echo "== 5. waiting for $URL"
code="000"
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
  if [ "$code" = "200" ]; then
    echo "   live: $URL (HTTP 200)"
    exit 0
  fi
  sleep 15
done
echo "   !! still HTTP $code — check the build at https://github.com/$OWNER/$REPO/actions"
exit 4
