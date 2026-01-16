"""
Test script to interact with the LoCo Agent server and ask it to list files
"""

import asyncio
import json
import httpx
import websockets

BASE_URL = "http://127.0.0.1:3199"
WS_URL = "ws://127.0.0.1:3199"


async def test_list_files():
    """Test the agent's ability to list files"""

    # Step 1: Register workspace
    print("1. Registering workspace...")
    async with httpx.AsyncClient() as client:
        workspace_response = await client.post(
            f"{BASE_URL}/v1/workspaces/register",
            json={
                "path": r"c:\Users\Kevin\Projects\LoCo",
                "name": "LoCo Test",
                "module_id": "vscode",
                "auto_index": False,
                "auto_watch": False
            }
        )
        workspace_data = workspace_response.json()
        workspace_id = workspace_data["id"]
        print(f"   Workspace registered: {workspace_id}")

    # Step 2: Create session
    print("\n2. Creating session...")
    async with httpx.AsyncClient() as client:
        session_response = await client.post(
            f"{BASE_URL}/v1/sessions",
            json={
                "workspace_id": workspace_id
            }
        )
        session_data = session_response.json()
        session_id = session_data["id"]
        print(f"   Session created: {session_id}")

    # Step 3: Connect to WebSocket and ask to list files
    print("\n3. Connecting to WebSocket...")
    ws_url = f"{WS_URL}/v1/sessions/{session_id}/stream"

    async with websockets.connect(ws_url) as websocket:
        print("   Connected!")

        # Receive server hello
        server_hello = await websocket.recv()
        print(f"\n4. Server hello received:")
        print(f"   {json.loads(server_hello)}")

        # Send client hello
        print("\n5. Sending client hello...")
        await websocket.send(json.dumps({
            "type": "client.hello",
            "client_info": {
                "name": "test_script",
                "version": "1.0.0"
            }
        }))

        # Send user message asking to list files
        print("\n6. Sending message: 'Please list the files in the current directory'...")
        await websocket.send(json.dumps({
            "type": "client.user_message",
            "message": "Please list the files in the current directory (the workspace root directory)",
            "context": {
                "module_id": "vscode"
            }
        }))

        # Receive and print all responses
        print("\n7. Receiving responses:\n")
        print("=" * 80)

        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")

                if msg_type == "server.assistant_message":
                    print(f"\n[ASSISTANT MESSAGE]")
                    print(data.get("message", ""))

                elif msg_type == "server.thinking":
                    print(f"\n[THINKING]")
                    print(data.get("content", ""))

                elif msg_type == "server.tool_use":
                    print(f"\n[TOOL USE: {data.get('tool_name')}]")
                    print(f"Input: {json.dumps(data.get('input', {}), indent=2)}")

                elif msg_type == "server.tool_result":
                    print(f"\n[TOOL RESULT]")
                    result = data.get("result", {})
                    print(json.dumps(result, indent=2))

                elif msg_type == "server.response_complete":
                    print("\n" + "=" * 80)
                    print("[RESPONSE COMPLETE]")
                    break

                elif msg_type == "server.error":
                    print(f"\n[ERROR]")
                    print(json.dumps(data.get("error", {}), indent=2))
                    break

                else:
                    print(f"\n[{msg_type.upper()}]")
                    print(json.dumps(data, indent=2))

            except json.JSONDecodeError:
                print(f"[RAW] {message}")


if __name__ == "__main__":
    asyncio.run(test_list_files())
