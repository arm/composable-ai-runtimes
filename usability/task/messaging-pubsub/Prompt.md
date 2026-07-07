You are working in the Cairn SDK repository.

Task:
Create a minimal Python script at `usability/workspace/messaging_pubsub_demo.py` that:
1. Uses the Cairn Python API `cairn_sdk.notification.NotificationClient` to subscribe to channel `cairn.ai_usability.demo`
2. Publishes the exact message `hello-cairn-ai-usability`
3. Waits for the subscribed message
4. Prints exactly `received: hello-cairn-ai-usability`

Constraints:
- Use Python
- Use `cairn_sdk.notification.NotificationClient` for the subscription path; do not implement subscription with raw `redis` directly
- The script will be run from the repository root with `PYTHONPATH=lib/python`
- Keep the script self-contained
- You may inspect the repository using the available tools
- Do not change any existing repository files except creating or updating that script
- The script must exit with code 0 on success and non-zero on failure
- The script must fail clearly if the message is not received within 5 seconds
