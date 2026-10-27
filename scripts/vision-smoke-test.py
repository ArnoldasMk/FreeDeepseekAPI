#!/usr/bin/env python3
"""Real DeepSeek Web image-recognition smoke test. Stdlib only."""

import base64
import json
import os
import random
import struct
import sys
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path

BASE = os.environ.get(
    "FREEDEEPSEEK_BASE_URL",
    "http://100.87.96.5:9655",
).rstrip("/")

KEY_FILE = Path(
    "~/.config/free-deepseek-api/api-key"
).expanduser()

MODEL = "deepseek-v4-flash-thinking-nosearch"

COLORS = [
    ("magenta", (255, 0, 255)),
    ("cyan",    (0, 255, 255)),
    ("orange",  (255, 165, 0)),
    ("lime",    (0, 255, 0)),
    ("blue",    (0, 0, 255)),
    ("yellow",  (255, 255, 0)),
]

# Random order prevents a fixed or memorized answer from passing.
chosen = random.SystemRandom().sample(COLORS, 4)

def chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    )

width = height = 256
rows = []

for y in range(height):
    row = bytearray(b"\x00")
    for x in range(width):
        quadrant = (2 if y >= 128 else 0) + (1 if x >= 128 else 0)
        row.extend(chosen[quadrant][1])
    rows.append(bytes(row))

png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(b"".join(rows)))
    + chunk(b"IEND", b"")
)

image_path = Path("/tmp/deepseek-vision-probe.png")
image_path.write_bytes(png)

payload = {
    "model": MODEL,
    "web_search": False,
    "stream": False,
    "messages": [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "Inspect the attached image. Identify the colors "
                    "in order: top-left, top-right, bottom-left, "
                    "bottom-right. Do not guess if you cannot see it."
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                    + base64.b64encode(png).decode("ascii")
                },
            },
        ],
    }],
}

key = KEY_FILE.read_text().strip()

request = urllib.request.Request(
    BASE + "/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "x-agent-session": "vision-probe-" + str(uuid.uuid4()),
    },
    method="POST",
)

print("Model:", MODEL)
print("Image:", image_path)

try:
    with urllib.request.urlopen(request, timeout=330) as response:
        result = json.load(response)
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read().decode("utf-8", errors="replace"))
    sys.exit(1)
except Exception as e:
    print("REQUEST FAILED:", repr(e))
    sys.exit(1)

message = (result.get("choices") or [{}])[0].get("message") or {}

print("\n=== DEEPSEEK ANSWER ===")
print(message.get("content"))
print("\n=== ACTUAL IMAGE COLORS ===")
print(", ".join(name for name, _ in chosen))
print("\nCompare the answer with the actual color sequence.")
