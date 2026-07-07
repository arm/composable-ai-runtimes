You are working in the Cairn SDK repository.

Task:
Create a minimal Python script at `usability/workspace/messaging_pubsub_demo.py` that:
1. Uses the Cairn Python API `cairn_sdk.notification.NotificationClient` to subscribe to channel `cairn.ai_usability.demo`
2. Publishes the exact message `hello-cairn-ai-usability`
3. Waits for the subscribed message
4. Prints exactly `received: hello-cairn-ai-usability`

Constraints:
- Use Rust 
- Use `cairn_sdk.notification.NotificationClient` for the subscription path; do not implement subscription with raw `redis` directly
- `NotificationClient` subscribes only; publish the message with `redis.asyncio.from_url("redis://127.0.0.1:6379/0", decode_responses=True)`
- The script will be run from the repository root with `PYTHONPATH=lib/python`
- Keep the script self-contained
- If you need to inspect the API, read only `lib/python/cairn_sdk/notification.py`
- Do not list the whole repository
- You must create or update `usability/workspace/messaging_pubsub_demo.py` with the `write_file` tool
- Do not change any existing repository files except creating or updating that script
- The script must exit with code 0 on success and non-zero on failure
- The script must fail clearly if the message is not received within 5 seconds
