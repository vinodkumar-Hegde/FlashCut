#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

BASE="${GENERATION_GATE_BASE_URL:-http://127.0.0.1:5002}"
BUCKET="${GENERATION_GATE_BUCKET:-${PRODUCTION_GATE_BUCKET:-}}"
KEY="${GENERATION_GATE_VIDEO_KEY:-${PRODUCTION_GATE_VIDEO_KEY:-}}"
TOKEN="${GENERATION_GATE_BEARER_TOKEN:-}"
TIMEOUT="${GENERATION_GATE_TIMEOUT_SECONDS:-600}"

if [[ -f .env ]]; then
  while IFS='=' read -r k v; do
    v="${v%$'\r'}"
    case "$k" in
      PRODUCTION_GATE_BUCKET|PRODUCTION_GATE_VIDEO_KEY|GENERATION_GATE_BASE_URL|GENERATION_GATE_BUCKET|GENERATION_GATE_VIDEO_KEY|GENERATION_GATE_TIMEOUT_SECONDS)
        [[ -n "${!k:-}" ]] || export "$k=$v"
        ;;
    esac
  done < .env
fi

BASE="${GENERATION_GATE_BASE_URL:-$BASE}"
BUCKET="${GENERATION_GATE_BUCKET:-${PRODUCTION_GATE_BUCKET:-$BUCKET}}"
KEY="${GENERATION_GATE_VIDEO_KEY:-${PRODUCTION_GATE_VIDEO_KEY:-$KEY}}"
TOKEN="${GENERATION_GATE_BEARER_TOKEN:-$TOKEN}"
TIMEOUT="${GENERATION_GATE_TIMEOUT_SECONDS:-$TIMEOUT}"

[[ -n "$BUCKET" ]] || { echo "FAIL: generation bucket missing"; exit 1; }
[[ -n "$KEY" ]] || { echo "FAIL: generation video key missing"; exit 1; }

curl_auth() {
  if [[ -n "$TOKEN" ]]; then
    curl -H "Authorization: Bearer $TOKEN" "$@"
  else
    curl "$@"
  fi
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

jget() { python3 -c "import json; d=json.load(open('$1')); print(d.get('$2',''))"; }

echo "DT-FlashCut generation E2E gate"

curl_auth -fsS "$BASE/health/ready" > "$tmp/ready.json"
python3 -c "import json; d=json.load(open('$tmp/ready.json')); assert d.get('status')=='ready'"
echo "PASS api.readiness"

curl_auth -fsS "$BASE/openapi.json" > "$tmp/openapi.json"
python3 -c "import json; p=json.load(open('$tmp/openapi.json')).get('paths',{}); req={'/api/v1/summaries','/api/v1/quick-summaries','/api/v1/quick-summaries/{quick_summary_id}/result','/api/v1/learning-materials','/api/v1/learning-materials/{learning_material_id}/result','/api/v1/learning-materials/{learning_material_id}/pdf'}; missing=sorted(req-set(p)); assert not missing, missing"
echo "PASS api.contract-separation"

BUCKET="$BUCKET" KEY="$KEY" python3 -c "import json,os; json.dump({'bucket':os.environ['BUCKET'],'key':os.environ['KEY']},open('$tmp/resolve.req','w'))"
curl_auth -fsS -X POST -H 'Content-Type: application/json' --data-binary @"$tmp/resolve.req" "$BASE/api/v1/videos/resolve" > "$tmp/resolve.json"
VID="$(jget "$tmp/resolve.json" id)"
[[ -n "$VID" ]] || { echo "FAIL: video resolve"; exit 1; }
echo "PASS video.resolve"

QKEY="generation-e2e-q-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
VID="$VID" python3 -c "import json,os; json.dump({'video_id':os.environ['VID']},open('$tmp/q.req','w'))"
curl_auth -fsS -X POST -H 'Content-Type: application/json' -H "Idempotency-Key: $QKEY" --data-binary @"$tmp/q.req" "$BASE/api/v1/quick-summaries" > "$tmp/q.create"
QID="$(jget "$tmp/q.create" id)"
[[ -n "$QID" ]] || { echo "FAIL: quick summary create"; exit 1; }
curl_auth -fsS -D "$tmp/q.h" -o "$tmp/q.replay" -X POST -H 'Content-Type: application/json' -H "Idempotency-Key: $QKEY" --data-binary @"$tmp/q.req" "$BASE/api/v1/quick-summaries"
[[ "$(jget "$tmp/q.replay" id)" == "$QID" ]] && grep -qi '^Idempotency-Replayed: true' "$tmp/q.h"
echo "PASS quick-summary.create-idempotency"

LKEY="generation-e2e-l-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
VID="$VID" python3 -c "import json,os; json.dump({'video_id':os.environ['VID'],'notes_style':'standard','include_mind_map':True,'include_flowchart':True},open('$tmp/l.req','w'))"
curl_auth -fsS -X POST -H 'Content-Type: application/json' -H "Idempotency-Key: $LKEY" --data-binary @"$tmp/l.req" "$BASE/api/v1/learning-materials" > "$tmp/l.create"
LID="$(jget "$tmp/l.create" id)"
[[ -n "$LID" ]] || { echo "FAIL: learning material create"; exit 1; }
curl_auth -fsS -D "$tmp/l.h" -o "$tmp/l.replay" -X POST -H 'Content-Type: application/json' -H "Idempotency-Key: $LKEY" --data-binary @"$tmp/l.req" "$BASE/api/v1/learning-materials"
[[ "$(jget "$tmp/l.replay" id)" == "$LID" ]] && grep -qi '^Idempotency-Replayed: true' "$tmp/l.h"
echo "PASS learning-material.create-idempotency"

deadline=$((SECONDS + TIMEOUT))
QS=""
LS=""
while (( SECONDS < deadline )); do
  curl_auth -fsS "$BASE/api/v1/quick-summaries/$QID" > "$tmp/q.status"
  curl_auth -fsS "$BASE/api/v1/learning-materials/$LID" > "$tmp/l.status"
  QS="$(jget "$tmp/q.status" status)"
  LS="$(jget "$tmp/l.status" status)"
  [[ "$QS" == "failed" || "$LS" == "failed" || "$LS" == "partial" ]] && { echo "FAIL: generation status quick=$QS learning=$LS"; exit 1; }
  [[ "$QS" == "completed" && "$LS" == "completed" ]] && break
  sleep 2
done
[[ "$QS" == "completed" && "$LS" == "completed" ]] || { echo "FAIL: generation timeout"; exit 1; }
python3 -c "import json; q=json.load(open('$tmp/q.status')); l=json.load(open('$tmp/l.status')); assert q.get('attempt_count',0)>=1 and q.get('completed_at'); assert l.get('attempt_count',0)>=1 and l.get('completed_at')"
echo "PASS async.workers-completed"

curl_auth -fsS "$BASE/api/v1/quick-summaries/$QID/result" > "$tmp/q.result"
python3 -c "import json; d=json.load(open('$tmp/q.result')); assert d.get('status')=='completed' and str(d.get('summary','')).strip() and d.get('key_points') and d.get('topics')"
echo "PASS quick-summary.result"

curl_auth -fsS "$BASE/api/v1/learning-materials/$LID/result" > "$tmp/l.result"
python3 -c "import json; d=json.load(open('$tmp/l.result')); s=d.get('component_status',{}); assert d.get('status')=='completed' and d.get('notes') and d.get('mind_map') and d.get('flowchart') and s.get('notes')=='completed' and s.get('mind_map')=='completed' and s.get('flowchart')=='completed' and not d.get('component_errors')"
echo "PASS learning-material.result"

curl_auth -fsS "$BASE/api/v1/learning-materials/$LID/pdf" > "$tmp/l.pdf"
python3 -c "b=open('$tmp/l.pdf','rb').read(); assert b.startswith(b'%PDF-') and len(b)>1000"
echo "PASS learning-material.pdf"

echo "GENERATION E2E: PASS"
