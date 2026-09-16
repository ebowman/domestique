"""Fixed future GitHub release transport and closed, non-extracting tar decoder.

Checksums detect corruption, not independent publisher authentication. No
candidate code is executed here; no requests/third-party networking libraries.
"""
import gzip
import io
import os
import selectors
import shutil
import subprocess
import tarfile
import time
from urllib.parse import urljoin, urlsplit
from .safe import META_LIMIT, PAYLOAD_LIMIT, Refusal, need, sha, text_bounds, re
from .package import DIRS, LEAVES, VERSION

HOSTS = ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com")


def release_url(version, sidecar=False):
    need(re.fullmatch(VERSION, version), "invalid official version")
    name = "domestique2-" + version + ".tar.gz"
    return ("https://github.com/ebowman/domestique/releases/download/v" +
            version + "/" + name + (".sha256" if sidecar else ""))


def https_release(url):
    parts = urlsplit(url)
    need(parts.scheme == "https" and parts.netloc in HOSTS and not parts.fragment and
         not any(ord(c) <= 32 or ord(c) >= 127 for c in url),
         "release redirect outside HTTPS allowlist")


def curl_response(url, cap, remaining, env):
    """One bounded response including headers. Kill/reap only our direct child."""
    curl = shutil.which("curl", path=env.get("PATH", ""))
    need(curl, "curl unavailable")
    argv = [curl, "-q", "--silent", "--show-error", "--fail",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "10", "--max-time", str(remaining),
            "--retry", "0", "--proxy", "", "--noproxy", "*",
            "--max-filesize", str(cap), "--dump-header", "-", "--", url]
    process = subprocess.Popen(argv, env={"PATH": env.get("PATH", os.defpath), "LC_ALL": "C"},
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    end = time.monotonic() + remaining
    output = bytearray()
    header_end = None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                left = end - time.monotonic()
                need(left > 0 and selector.select(left), "release fetch timeout")
                # Even a chunk straddling the header/body boundary can consume
                # at most the remaining body budget plus one overflow witness.
                size = (min(cap + 1, META_LIMIT + 1 - len(output))
                        if header_end is None else cap + 1 - (len(output) - header_end))
                chunk = os.read(process.stdout.fileno(), min(65536, size))
                if not chunk:
                    break
                search = max(0, len(output) - 3)
                output.extend(chunk)
                if header_end is None:
                    separator = output.find(b"\r\n\r\n", search)
                    if separator >= 0:
                        header_end = separator + 4
                    need((len(output) if header_end is None else header_end) <= META_LIMIT,
                         "release response header too large")
                if header_end is not None:
                    need(len(output) - header_end <= cap, "release response too large")
        need(process.wait(timeout=max(.001, end - time.monotonic())) == 0,
             "release fetch failed")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def fetch_asset(url, cap, env):
    deadline = time.monotonic() + 120
    budget = cap
    for redirects in range(4):
        https_release(url)
        left = deadline - time.monotonic()
        need(left > 0, "release fetch timeout")
        response = curl_response(url, budget, left, env)
        header, separator, body = response.partition(b"\r\n\r\n")
        need(separator and len(header) + 4 <= META_LIMIT and len(body) <= budget,
             "invalid/oversize release response")
        budget -= len(body)
        lines = header.split(b"\r\n")
        need(len(lines) <= 16384 and all(len(x) + 2 <= 8192 for x in lines),
             "response header bounds")
        match = re.fullmatch(rb"HTTP/(?:1\.[01]|2|3) ([0-9]{3})(?: [^\r\n]*)?", lines[0])
        need(match is not None, "invalid release HTTP status")
        fields = {}
        for line in lines[1:]:
            key, sep, value = line.partition(b":")
            need(sep and re.fullmatch(rb"[A-Za-z0-9-]+", key), "invalid HTTP field")
            key = key.lower()
            if key in (b"location", b"content-length"):
                need(key not in fields, "duplicate HTTP selection field")
                fields[key] = value.strip()
        status = int(match[1])
        if b"content-length" in fields:
            size = fields[b"content-length"]
            need(re.fullmatch(rb"0|[1-9][0-9]*", size) and len(size) < 20 and
                 int(size) == len(body), "truncated release response")
        if status in (301, 302, 303, 307, 308):
            need(redirects < 3 and b"location" in fields, "release redirect limit/location")
            url = urljoin(url, fields[b"location"].decode("ascii"))
            continue
        need(status == 200, "release unavailable")
        return body
    raise Refusal("release redirect limit")


def archive_data(archive, sidecar, version):
    """Verify archive BEFORE parsing; inspect every raw header before staging.

    Deliberately reject GNU/PAX extension records as extra inventory rather than
    letting tarfile silently hide them. Fixed leaf names need no extensions.
    Never tar.extract/all; archive owners, modes and timestamps are ignored.
    """
    need(len(archive) <= PAYLOAD_LIMIT, "archive cap")
    text_bounds(sidecar)
    name = "domestique2-" + version + ".tar.gz"
    need(sidecar == (sha(archive) + "  " + name + "\n").encode(),
         "archive sidecar format/digest")
    # Bound decompression including tar framing, not merely member-size claims.
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        raw = stream.read(PAYLOAD_LIMIT + 1)
    need(len(raw) <= PAYLOAD_LIMIT and len(raw) % 512 == 0,
         "expanded archive cap/framing")
    directories = {"domestique2", *("domestique2/" + p for p in DIRS)}
    leaves = {"domestique2/" + p for p in LEAVES}
    seen, data, offset, total = set(), {}, 0, 0
    while offset + 512 <= len(raw) and raw[offset:offset + 512] != bytes(512):
        info = tarfile.TarInfo.frombuf(raw[offset:offset + 512], "utf-8", "strict")
        path = info.name
        need(path not in seen and path in directories | leaves, "archive inventory/path")
        seen.add(path)
        directory = path in directories
        need(info.type == tarfile.DIRTYPE if directory else
             info.type in (tarfile.REGTYPE, tarfile.AREGTYPE),
             "archive links/extensions/nonregular member")
        need(not info.linkname and not info.pax_headers and info.size >= 0,
             "archive link/size")
        size = info.size
        need(size == 0 if directory else size <= (
            META_LIMIT if path in ("domestique2/PACKAGE", "domestique2/SHA256SUMS")
            else PAYLOAD_LIMIT), "archive member cap")
        start = offset + 512
        offset = start + ((size + 511) // 512) * 512
        need(offset <= len(raw), "truncated archive member")
        if not directory:
            total += size
            need(total <= PAYLOAD_LIMIT, "expanded payload cap")
            data[path[len("domestique2/"):]] = raw[start:start + size]
    need(seen == directories | leaves and len(raw) - offset >= 1024 and
         not any(raw[offset:]), "incomplete/extra/truncated archive")
    return data


def fetch_package(version, env):
    sidecar = fetch_asset(release_url(version, True), META_LIMIT, env)
    archive = fetch_asset(release_url(version), PAYLOAD_LIMIT, env)
    return archive_data(archive, sidecar, version)
