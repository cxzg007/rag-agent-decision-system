import json
import sys


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("ascii").strip()
        if not line:
            break
        key, value = line.split(":", 1)
        headers[key.lower()] = value.strip()
    length = int(headers["content-length"])
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def write_message(payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    sys.stdout.buffer.flush()


while True:
    message = read_message()
    if message is None:
        break
    method = message.get("method")
    if method == "initialize":
        write_message({"jsonrpc": "2.0", "id": message["id"], "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/call":
        params = message.get("params", {})
        write_message(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"echo:{params.get('arguments', {}).get('text', '')}",
                        }
                    ],
                    "isError": False,
                },
            }
        )
    else:
        write_message({"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32601, "message": "method not found"}})
