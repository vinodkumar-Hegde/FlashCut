import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
import sys
import time
import uuid
from pathlib import PurePosixPath
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)


LOCAL_URL = (
    os.getenv(
        "PRODUCTION_GATE_BASE_URL",
        "http://127.0.0.1:5002",
    )
    .strip()
    .rstrip("/")
)

MODE = (
    os.getenv(
        "PRODUCTION_GATE_MODE",
        "local",
    )
    .strip()
    .lower()
)

LOCAL_BUCKET = (
    os.getenv(
        "PRODUCTION_GATE_BUCKET",
        "transcript-video-prototype-dev",
    )
    .strip()
)

LOCAL_VIDEO_KEY = (
    os.getenv(
        "PRODUCTION_GATE_VIDEO_KEY",
        "videos/Ortho-Demo.mp4",
    )
    .strip()
)


results = []


def shell(
    command,
    *,
    timeout=120,
):
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )

    return (
        result.returncode,
        result.stdout,
        result.stderr,
    )


def http(
    method,
    url,
    *,
    headers=None,
    body=None,
    timeout=30,
):
    headers = dict(
        headers
        or {}
    )

    data = None

    if body is not None:
        if isinstance(
            body,
            (
                dict,
                list,
            ),
        ):
            data = json.dumps(
                body
            ).encode(
                "utf-8"
            )

            headers.setdefault(
                "Content-Type",
                "application/json",
            )

        elif isinstance(
            body,
            str,
        ):
            data = body.encode(
                "utf-8"
            )

        else:
            data = body

    request = Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read()

            return (
                response.status,
                {
                    key.lower():
                        value
                    for (
                        key,
                        value,
                    )
                    in response.headers.items()
                },
                raw.decode(
                    "utf-8",
                    errors="replace",
                ),
            )

    except HTTPError as exc:
        raw = exc.read()

        return (
            exc.code,
            {
                key.lower():
                    value
                for (
                    key,
                    value,
                )
                in exc.headers.items()
            },
            raw.decode(
                "utf-8",
                errors="replace",
            ),
        )

    except URLError as exc:
        raise RuntimeError(
            f"HTTP connection failed: {exc}"
        ) from exc


def json_body(
    raw,
):
    try:
        return json.loads(
            raw
        )

    except Exception:
        return {}


def error_code(
    raw,
):
    data = json_body(
        raw
    )

    return (
        data.get(
            "error",
            {},
        )
        .get(
            "code"
        )
    )


def pass_result(
    name,
    detail="",
):
    results.append(
        (
            name,
            True,
            detail,
        )
    )

    print(
        f"PASS  {name}"
        + (
            f" — {detail}"
            if detail
            else ""
        )
    )


def fail_result(
    name,
    detail,
):
    results.append(
        (
            name,
            False,
            detail,
        )
    )

    print(
        f"FAIL  {name} — {detail}"
    )


def check(
    name,
    function,
):
    try:
        detail = function()

    except Exception as exc:
        fail_result(
            name,
            str(exc),
        )

        return

    pass_result(
        name,
        str(
            detail
            or ""
        ),
    )


def require(
    condition,
    message,
):
    if not condition:
        raise AssertionError(
            message
        )


def local_api_ready():
    status, _, raw = http(
        "GET",
        LOCAL_URL
        + "/health/ready",
    )

    require(
        status == 200,
        (
            "readiness returned "
            f"{status}: {raw}"
        ),
    )

    require(
        json_body(
            raw
        ).get(
            "status"
        )
        == "ready",
        raw,
    )


def get_local_video():
    status, _, raw = http(
        "GET",
        LOCAL_URL
        + "/api/v1/videos",
    )

    require(
        status == 200,
        (
            "video listing failed: "
            f"{status} {raw}"
        ),
    )

    items = (
        json_body(
            raw
        ).get(
            "items"
        )
        or []
    )

    require(
        items,
        "No local videos available.",
    )

    for item in items:
        if (
            item.get(
                "name"
            )
            == PurePosixPath(
                LOCAL_VIDEO_KEY
            ).name
        ):
            return item

    return items[0]


def test_compose():
    code, _, err = shell(
        "docker compose "
        "-f docker-compose.yml "
        "config >/dev/null"
    )

    require(
        code == 0,
        err,
    )


def test_containers():
    code, out, err = shell(
        "docker compose "
        "-f docker-compose.yml "
        "ps --format json"
    )

    require(
        code == 0,
        err,
    )

    require(
        "flashcut-api"
        in out,
        "API container missing.",
    )

    require(
        "flashcut-postgres"
        in out,
        "Postgres container missing.",
    )

    require(
        "flashcut-redis"
        in out,
        "Redis container missing.",
    )


def test_redis():
    code, out, err = shell(
        "docker exec "
        "flashcut-redis "
        "redis-cli ping"
    )

    require(
        code == 0,
        err,
    )

    require(
        out.strip()
        == "PONG",
        out,
    )


def test_alembic():
    code, out, err = shell(
        "docker compose "
        "-f docker-compose.yml "
        "exec -T production-api "
        "alembic "
        "-c /app/alembic.ini "
        "current"
    )

    require(
        code == 0,
        err,
    )

    require(
        "0013"
        in out,
        (
            "Expected migration "
            "0013 head."
        ),
    )


def test_security_headers():
    status, headers, raw = http(
        "GET",
        LOCAL_URL
        + "/api/v1/videos",
    )

    require(
        status == 200,
        raw,
    )

    expected = {
        "x-request-id",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
        "cache-control",
        "content-security-policy",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
    }

    missing = sorted(
        expected
        - set(
            headers
        )
    )

    require(
        not missing,
        (
            "Missing headers: "
            + ", ".join(
                missing
            )
        ),
    )


def test_request_size():
    body = json.dumps(
        {
            "payload":
                "x"
                * 2_000_100
        }
    ).encode(
        "utf-8"
    )

    with tempfile.NamedTemporaryFile(
        prefix="flashcut-gate-",
        suffix=".json",
    ) as tmp:
        tmp.write(
            body
        )

        tmp.flush()

        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-o",
                "-",
                "-w",
                "\\n%{http_code}",
                "-X",
                "POST",
                LOCAL_URL
                + "/api/v1/notes",
                "-H",
                (
                    "Content-Type: "
                    "application/json"
                ),
                "--data-binary",
                "@"
                + tmp.name,
            ],
            text=True,
            capture_output=True,
            timeout=30,
        )

    require(
        result.returncode == 0,
        (
            result.stderr
            or result.stdout
        ),
    )

    raw, separator, code = (
        result.stdout.rpartition(
            "\n"
        )
    )

    require(
        separator,
        (
            "Could not parse curl "
            "HTTP status."
        ),
    )

    require(
        code.strip()
        == "413",
        (
            "Expected 413, "
            f"received {code.strip()}: "
            f"{raw}"
        ),
    )

    require(
        error_code(
            raw
        )
        == "REQUEST_TOO_LARGE",
        raw,
    )


def local_rate_key():
    tenant = (
        "local-development"
    )

    subject = (
        "local-development"
    )

    identity = hashlib.sha256(
        (
            tenant
            + "\0"
            + subject
        ).encode()
    ).hexdigest()

    bucket = int(
        time.time()
        // 60
    )

    return (
        "flashcut:rate:"
        f"{identity}:"
        f"all:{bucket}"
    )


def test_rate_limit():
    remaining = (
        60
        - int(
            time.time()
            % 60
        )
    )

    if remaining < 5:
        time.sleep(
            remaining
            + 1
        )

    key = local_rate_key()

    try:
        code, out, err = shell(
            "docker exec "
            "flashcut-redis "
            "redis-cli SET "
            f"'{key}' 300 EX 70"
        )

        require(
            code == 0,
            err,
        )

        require(
            "OK"
            in out,
            out,
        )

        status, headers, raw = http(
            "GET",
            LOCAL_URL
            + "/api/v1/videos",
        )

        require(
            status == 429,
            (
                "Expected 429, "
                f"received {status}: "
                f"{raw}"
            ),
        )

        require(
            error_code(
                raw
            )
            == "RATE_LIMIT_EXCEEDED",
            raw,
        )

        require(
            headers.get(
                "ratelimit-remaining"
            )
            == "0",
            str(
                headers
            ),
        )

        require(
            "retry-after"
            in headers,
            str(
                headers
            ),
        )

    finally:
        shell(
            "docker exec "
            "flashcut-redis "
            "redis-cli DEL "
            f"'{key}'"
        )


def test_rate_limit_recovery():
    status, _, raw = http(
        "GET",
        LOCAL_URL
        + "/api/v1/videos",
    )

    require(
        status == 200,
        raw,
    )


def test_resolver_valid():
    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/videos/resolve",
        body={
            "bucket":
                LOCAL_BUCKET,

            "key":
                LOCAL_VIDEO_KEY,
        },
    )

    require(
        status
        in {
            200,
            201,
        },
        raw,
    )

    data = json_body(
        raw
    )

    forbidden = {
        "bucket",
        "s3_key",
        "url",
    }

    require(
        not (
            forbidden
            & set(
                data
            )
        ),
        (
            "Resolver exposed "
            "source internals."
        ),
    )


def test_resolver_wrong_bucket():
    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/videos/resolve",
        body={
            "bucket":
                "__production_gate_wrong__",

            "key":
                LOCAL_VIDEO_KEY,
        },
    )

    require(
        status == 403,
        raw,
    )

    require(
        error_code(
            raw
        )
        == "SOURCE_BUCKET_NOT_ALLOWED",
        raw,
    )


def test_resolver_prefix():
    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/videos/resolve",
        body={
            "bucket":
                LOCAL_BUCKET,

            "key":
                "private/"
                "__production_gate__.mp4",
        },
    )

    require(
        status == 400,
        raw,
    )

    require(
        error_code(
            raw
        )
        == "INVALID_VIDEO_KEY",
        raw,
    )


def test_resolver_etag():
    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/videos/resolve",
        body={
            "bucket":
                LOCAL_BUCKET,

            "key":
                LOCAL_VIDEO_KEY,

            "expected_etag":
                "__wrong_etag__",
        },
    )

    require(
        status == 409,
        raw,
    )

    require(
        error_code(
            raw
        )
        == "SOURCE_VERSION_MISMATCH",
        raw,
    )


def concurrent_post(
    path,
    *,
    payload,
    key,
    token=None,
    base_url=None,
):
    base_url = (
        base_url
        or LOCAL_URL
    )

    headers = {
        "Idempotency-Key":
            key,
    }

    if token:
        headers[
            "Authorization"
        ] = (
            "Bearer "
            + token
        )

    def call():
        status, _, raw = http(
            "POST",
            base_url
            + path,
            headers=headers,
            body=payload,
            timeout=60,
        )

        return (
            status,
            json_body(
                raw
            ),
            raw,
        )

    with (
        concurrent.futures
        .ThreadPoolExecutor(
            max_workers=2
        )
    ) as executor:
        return list(
            executor.map(
                lambda _:
                    call(),
                range(
                    2
                ),
            )
        )


def test_notes_idempotency():
    video = get_local_video()

    key = (
        "gate-note-"
        + uuid.uuid4().hex
    )

    responses = concurrent_post(
        "/api/v1/notes",
        payload={
            "video_id":
                video["id"],

            "style":
                "standard",
        },
        key=key,
    )

    ids = []

    for status, data, raw in responses:
        require(
            status
            in {
                200,
                202,
            },
            raw,
        )

        ids.append(
            data.get(
                "id"
            )
        )

    require(
        ids[0]
        and ids[0]
        == ids[1],
        (
            "Concurrent Notes calls "
            "created different IDs: "
            f"{ids}"
        ),
    )

    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/notes",
        headers={
            "Idempotency-Key":
                key
        },
        body={
            "video_id":
                video["id"],

            "style":
                "crisp",
        },
    )

    require(
        status == 409,
        raw,
    )

    require(
        error_code(
            raw
        )
        == "IDEMPOTENCY_CONFLICT",
        raw,
    )


def test_selection_idempotency():
    video = get_local_video()

    key = (
        "gate-selection-"
        + uuid.uuid4().hex
    )

    responses = concurrent_post(
        "/api/v1/selections",
        payload={
            "video_id":
                video["id"]
        },
        key=key,
    )

    ids = []

    for status, data, raw in responses:
        require(
            status
            in {
                200,
                201,
            },
            raw,
        )

        ids.append(
            data.get(
                "id"
            )
        )

    require(
        ids[0]
        and ids[0]
        == ids[1],
        (
            "Concurrent Selection "
            "calls created different "
            f"IDs: {ids}"
        ),
    )

    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/selections",
        headers={
            "Idempotency-Key":
                key
        },
        body={
            "video_id":
                video["id"],

            "summary_id":
                "different-request",
        },
    )

    require(
        status == 409,
        raw,
    )

    require(
        error_code(
            raw
        )
        == "IDEMPOTENCY_CONFLICT",
        raw,
    )


def psql_scalar(
    sql,
):
    result = subprocess.run(
        [
            "docker",
            "exec",
            "flashcut-postgres",
            "psql",
            "-U",
            "doctutorials",
            "-d",
            "doctutorials",
            "-tAc",
            sql,
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )

    require(
        result.returncode == 0,
        result.stderr,
    )

    return (
        result.stdout.strip()
    )


def test_audit_events():
    count = psql_scalar(
        """
        SELECT count(*)
        FROM audit_events
        WHERE
            error_code IN (
                'REQUEST_TOO_LARGE',
                'SOURCE_BUCKET_NOT_ALLOWED'
            );
        """
    )

    require(
        int(
            count
            or "0"
        )
        >= 2,
        (
            "Expected security failures "
            "in audit_events."
        ),
    )


def test_logs_no_secrets():
    code, out, err = shell(
        "docker logs "
        "--tail 500 "
        "flashcut-api "
        "2>&1"
    )

    require(
        code == 0,
        err,
    )

    lower = out.lower()

    forbidden = [
        "aws_secret_access_key",
        "aws_session_token",
        "begin private key",
    ]

    found = [
        item
        for item
        in forbidden
        if item
        in lower
    ]

    require(
        not found,
        (
            "Sensitive material found "
            "in logs: "
            + ", ".join(
                found
            )
        ),
    )


def test_no_stacktrace_response():
    status, _, raw = http(
        "POST",
        LOCAL_URL
        + "/api/v1/notes",
        body={},
    )

    require(
        status == 422,
        raw,
    )

    lowered = raw.lower()

    require(
        "traceback"
        not in lowered,
        (
            "Traceback exposed "
            "to API client."
        ),
    )

    require(
        "/app/"
        not in lowered,
        (
            "Internal filesystem path "
            "exposed to client."
        ),
    )


def run_external_script(
    env_name,
):
    script = (
        os.getenv(
            env_name,
            ""
        )
        .strip()
    )

    require(
        script,
        (
            f"{env_name} is required "
            "for production sign-off."
        ),
    )

    require(
        os.path.isfile(
            script
        ),
        (
            f"Script not found: "
            f"{script}"
        ),
    )

    code = subprocess.run(
        [
            script
        ],
        env=os.environ.copy(),
    ).returncode

    require(
        code == 0,
        (
            f"{env_name} exited "
            f"with {code}."
        ),
    )


def staging_environment():
    names = [
        "PRODUCTION_GATE_STAGING_URL",
        "PRODUCTION_GATE_TOKEN_A",
        "PRODUCTION_GATE_TOKEN_B",
        "PRODUCTION_GATE_VIDEO_A",
        "PRODUCTION_GATE_VIDEO_B",
        "PRODUCTION_GATE_STAGING_BUCKET",
        "PRODUCTION_GATE_KEY_A",
        "PRODUCTION_GATE_KEY_B",
        "PRODUCTION_GATE_ETAG_A",
    ]

    missing = [
        name
        for name in names
        if not (
            os.getenv(
                name,
                ""
            )
            .strip()
        )
    ]

    require(
        not missing,
        (
            "Missing staging variables: "
            + ", ".join(
                missing
            )
        ),
    )

    return {
        name:
            os.environ[
                name
            ].strip()
        for name in names
    }


def auth_headers(
    token,
):
    return {
        "Authorization":
            "Bearer "
            + token
    }


def run_staging_tests():
    env = staging_environment()

    url = env[
        "PRODUCTION_GATE_STAGING_URL"
    ].rstrip("/")

    token_a = env[
        "PRODUCTION_GATE_TOKEN_A"
    ]

    token_b = env[
        "PRODUCTION_GATE_TOKEN_B"
    ]

    video_a = env[
        "PRODUCTION_GATE_VIDEO_A"
    ]

    video_b = env[
        "PRODUCTION_GATE_VIDEO_B"
    ]

    bucket = env[
        "PRODUCTION_GATE_STAGING_BUCKET"
    ]

    key_a = env[
        "PRODUCTION_GATE_KEY_A"
    ]

    key_b = env[
        "PRODUCTION_GATE_KEY_B"
    ]

    etag_a = env[
        "PRODUCTION_GATE_ETAG_A"
    ]


    def https_only():
        require(
            url.startswith(
                "https://"
            ),
            (
                "Staging endpoint "
                "must use HTTPS."
            ),
        )


    def staging_ready():
        status, _, raw = http(
            "GET",
            url
            + "/health/ready",
        )

        require(
            status == 200,
            raw,
        )


    def no_token():
        status, _, raw = http(
            "GET",
            url
            + "/api/v1/videos",
        )

        require(
            status == 401,
            raw,
        )


    def garbage_token():
        status, _, raw = http(
            "GET",
            url
            + "/api/v1/videos",
            headers=auth_headers(
                "not-a-valid-jwt"
            ),
        )

        require(
            status == 401,
            raw,
        )


    def tenant_a_valid():
        status, _, raw = http(
            "GET",
            url
            + "/api/v1/videos",
            headers=auth_headers(
                token_a
            ),
        )

        require(
            status == 200,
            raw,
        )


    def tenant_b_valid():
        status, _, raw = http(
            "GET",
            url
            + "/api/v1/videos",
            headers=auth_headers(
                token_b
            ),
        )

        require(
            status == 200,
            raw,
        )


    def a_cannot_read_b():
        status, _, raw = http(
            "GET",
            (
                url
                + "/api/v1/videos/"
                + video_b
                + "/transcript"
            ),
            headers=auth_headers(
                token_a
            ),
        )

        require(
            status == 404,
            (
                "Tenant A accessed "
                "Tenant B resource: "
                f"{status} {raw}"
            ),
        )


    def b_cannot_read_a():
        status, _, raw = http(
            "GET",
            (
                url
                + "/api/v1/videos/"
                + video_a
                + "/transcript"
            ),
            headers=auth_headers(
                token_b
            ),
        )

        require(
            status == 404,
            (
                "Tenant B accessed "
                "Tenant A resource: "
                f"{status} {raw}"
            ),
        )


    def resolve_own():
        status, _, raw = http(
            "POST",
            url
            + "/api/v1/videos/resolve",
            headers=auth_headers(
                token_a
            ),
            body={
                "bucket":
                    bucket,

                "key":
                    key_a,

                "expected_etag":
                    etag_a,
            },
        )

        require(
            status
            in {
                200,
                201,
            },
            raw,
        )


    def cross_tenant_s3():
        status, _, raw = http(
            "POST",
            url
            + "/api/v1/videos/resolve",
            headers=auth_headers(
                token_a
            ),
            body={
                "bucket":
                    bucket,

                "key":
                    key_b,
            },
        )

        require(
            status
            in {
                400,
                403,
            },
            (
                "Cross-tenant S3 key "
                "was not blocked: "
                f"{status} {raw}"
            ),
        )


    def wrong_bucket():
        status, _, raw = http(
            "POST",
            url
            + "/api/v1/videos/resolve",
            headers=auth_headers(
                token_a
            ),
            body={
                "bucket":
                    "__wrong_bucket__",

                "key":
                    key_a,
            },
        )

        require(
            status == 403,
            raw,
        )


    def stale_etag():
        status, _, raw = http(
            "POST",
            url
            + "/api/v1/videos/resolve",
            headers=auth_headers(
                token_a
            ),
            body={
                "bucket":
                    bucket,

                "key":
                    key_a,

                "expected_etag":
                    "__wrong_etag__",
            },
        )

        require(
            status == 409,
            raw,
        )


    def missing_object():
        path = PurePosixPath(
            key_a
        )

        missing = str(
            path.parent
            / (
                "__production_gate_missing_"
                + uuid.uuid4().hex
                + path.suffix
            )
        )

        status, _, raw = http(
            "POST",
            url
            + "/api/v1/videos/resolve",
            headers=auth_headers(
                token_a
            ),
            body={
                "bucket":
                    bucket,

                "key":
                    missing,
            },
        )

        require(
            status == 404,
            raw,
        )


    def staging_headers():
        status, headers, raw = http(
            "GET",
            url
            + "/api/v1/videos",
            headers=auth_headers(
                token_a
            ),
        )

        require(
            status == 200,
            raw,
        )

        required = {
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "cache-control",
            "ratelimit-limit",
        }

        missing = required - set(
            headers
        )

        require(
            not missing,
            (
                "Missing production "
                "headers: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            ),
        )


    def tenant_idempotency():
        key = (
            "cross-tenant-"
            + uuid.uuid4().hex
        )

        payload_a = {
            "video_id":
                video_a
        }

        payload_b = {
            "video_id":
                video_b
        }

        status_a, _, raw_a = http(
            "POST",
            url
            + "/api/v1/selections",
            headers={
                **auth_headers(
                    token_a
                ),
                "Idempotency-Key":
                    key,
            },
            body=payload_a,
        )

        status_b, _, raw_b = http(
            "POST",
            url
            + "/api/v1/selections",
            headers={
                **auth_headers(
                    token_b
                ),
                "Idempotency-Key":
                    key,
            },
            body=payload_b,
        )

        require(
            status_a
            in {
                200,
                201,
            },
            raw_a,
        )

        require(
            status_b
            in {
                200,
                201,
            },
            raw_b,
        )

        id_a = json_body(
            raw_a
        ).get(
            "id"
        )

        id_b = json_body(
            raw_b
        ).get(
            "id"
        )

        require(
            id_a
            and id_b
            and id_a != id_b,
            (
                "Idempotency key leaked "
                "across tenants."
            ),
        )


    check(
        "staging.https",
        https_only,
    )

    check(
        "staging.readiness",
        staging_ready,
    )

    check(
        "auth.missing-token",
        no_token,
    )

    check(
        "auth.invalid-token",
        garbage_token,
    )

    check(
        "auth.tenant-a",
        tenant_a_valid,
    )

    check(
        "auth.tenant-b",
        tenant_b_valid,
    )

    check(
        "tenant.a-cannot-read-b",
        a_cannot_read_b,
    )

    check(
        "tenant.b-cannot-read-a",
        b_cannot_read_a,
    )

    check(
        "s3.resolve-own",
        resolve_own,
    )

    check(
        "s3.cross-tenant",
        cross_tenant_s3,
    )

    check(
        "s3.wrong-bucket",
        wrong_bucket,
    )

    check(
        "s3.missing-object",
        missing_object,
    )

    check(
        "s3.stale-etag",
        stale_etag,
    )

    check(
        "security.production-headers",
        staging_headers,
    )

    check(
        "idempotency.cross-tenant",
        tenant_idempotency,
    )


def run_local_tests():
    check(
        "compose.configuration",
        test_compose,
    )

    check(
        "containers.required-services",
        test_containers,
    )

    check(
        "redis.health",
        test_redis,
    )

    check(
        "api.readiness",
        local_api_ready,
    )

    check(
        "database.migration-head",
        test_alembic,
    )

    check(
        "security.headers",
        test_security_headers,
    )

    check(
        "security.request-size",
        test_request_size,
    )

    check(
        "security.rate-limit",
        test_rate_limit,
    )

    check(
        "security.rate-limit-recovery",
        test_rate_limit_recovery,
    )

    check(
        "s3.resolve-valid",
        test_resolver_valid,
    )

    check(
        "s3.wrong-bucket",
        test_resolver_wrong_bucket,
    )

    check(
        "s3.prefix-isolation",
        test_resolver_prefix,
    )

    check(
        "s3.stale-etag",
        test_resolver_etag,
    )

    check(
        "idempotency.notes-concurrency",
        test_notes_idempotency,
    )

    check(
        "idempotency.selection-concurrency",
        test_selection_idempotency,
    )

    check(
        "audit.security-events",
        test_audit_events,
    )

    check(
        "logging.no-secrets",
        test_logs_no_secrets,
    )

    check(
        "security.no-stacktrace",
        test_no_stacktrace_response,
    )


def run_required_external_gates():
    scripts = [
        (
            "jwt.full-negative-suite",
            "PRODUCTION_GATE_JWT_NEGATIVE_SCRIPT",
        ),
        (
            "worker.failure-recovery",
            "PRODUCTION_GATE_FAILURE_RECOVERY_SCRIPT",
        ),
        (
            "workflow.full-e2e",
            "PRODUCTION_GATE_E2E_SCRIPT",
        ),
        (
            "load.multi-replica",
            "PRODUCTION_GATE_LOAD_SCRIPT",
        ),
        (
            "recovery.backup-restore",
            "PRODUCTION_GATE_BACKUP_RESTORE_SCRIPT",
        ),
        (
            "deployment.rollback",
            "PRODUCTION_GATE_ROLLBACK_SCRIPT",
        ),
    ]

    for (
        name,
        env_name,
    ) in scripts:
        check(
            name,
            lambda env_name=env_name:
                run_external_script(
                    env_name
                ),
        )


def print_summary():
    passed = sum(
        1
        for (
            _,
            ok,
            _,
        )
        in results
        if ok
    )

    failed = len(
        results
    ) - passed

    print()
    print(
        "=" * 68
    )
    print(
        "DT-FlashCut Production Grade Gate"
    )
    print(
        "=" * 68
    )

    for (
        name,
        ok,
        detail,
    ) in results:
        state = (
            "PASS"
            if ok
            else "FAIL"
        )

        print(
            f"{state:4}  {name}"
        )

        if (
            not ok
            and detail
        ):
            print(
                "      "
                + detail.replace(
                    "\n",
                    "\n      ",
                )
            )

    print(
        "-" * 68
    )

    print(
        f"PASSED: {passed}"
    )

    print(
        f"FAILED: {failed}"
    )

    print(
        f"TOTAL : {len(results)}"
    )

    print()

    if failed:
        print(
            "PRODUCTION GATE: FAIL"
        )

    else:
        print(
            "PRODUCTION GATE: PASS"
        )

    print(
        "=" * 68
    )

    return failed


def main():
    print(
        "DT-FlashCut production-grade test runner"
    )

    print(
        f"Mode: {MODE}"
    )

    print()

    if MODE not in {
        "local",
        "production",
    }:
        print(
            "PRODUCTION_GATE_MODE must "
            "be local or production."
        )

        return 2

    run_local_tests()

    if MODE == "production":
        check(
            "repository.clean",
            lambda:
                require(
                    shell(
                        "git status "
                        "--porcelain"
                    )[1].strip()
                    == "",
                    (
                        "Production sign-off "
                        "requires a clean "
                        "working tree."
                    ),
                ),
        )

        check(
            "production.destructive-approval",
            lambda:
                require(
                    (
                        os.getenv(
                            "PRODUCTION_GATE_ALLOW_DESTRUCTIVE",
                            "",
                        )
                        .strip()
                        .lower()
                        == "true"
                    ),
                    (
                        "Set "
                        "PRODUCTION_GATE_ALLOW_DESTRUCTIVE=true "
                        "for staging recovery tests."
                    ),
                ),
        )

        try:
            run_staging_tests()

        except Exception as exc:
            fail_result(
                "staging.configuration",
                str(
                    exc
                ),
            )

        run_required_external_gates()

    failed = print_summary()

    return (
        1
        if failed
        else 0
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )
