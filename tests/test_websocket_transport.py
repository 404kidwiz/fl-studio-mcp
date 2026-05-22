import asyncio
import pytest
import websockets
from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.transports.websocket import parse_ws_url


def test_parse_ws_url():
    assert parse_ws_url("ws://localhost:8765") == ("localhost", 8765)
    assert parse_ws_url("ws://127.0.0.1:1234") == ("127.0.0.1", 1234)
    assert parse_ws_url("ws://0.0.0.0") == ("0.0.0.0", 8765)
    assert parse_ws_url("wss://example.com:9999") == ("example.com", 9999)


@pytest.mark.asyncio
async def test_websocket_transport_communication():
    bridge = FLStudioBridge.get()

    # Connect using a specific local port
    port_name = "ws://127.0.0.1:8799"
    opened = bridge.connect(port_name)
    assert opened == port_name
    assert bridge.connected
    assert bridge.listening

    # Now, let's connect as a mock client to the WebSocket server
    async with websockets.connect(port_name) as client:
        # 1. Test sending from bridge to client
        # Let's send raw SysEx: F0 7F 7F 06 01 F7 (MIDI STOP)
        # Note: raw SysEx bytes must start with F0 and end with F7
        raw_msg = bytes([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])

        # Trigger sending bytes
        bridge.send_raw(raw_msg)

        # Client should receive the raw bytes
        received = await asyncio.wait_for(client.recv(), timeout=2.0)
        assert received == raw_msg

        # 2. Test sending from client to bridge
        # Let's send a SysEx back to the server using the FL-MCP Manufacturer ID (0x7D)
        # format: F0 7D <cmd> [payload] F7
        client_msg = bytes([0xF0, 0x7D, 0x01, 0x02, 0xF7])
        await client.send(client_msg)

        # The bridge's input callback should process this message and put it into response_queue
        # Wait for it to appear in response_queue
        deadline = asyncio.get_event_loop().time() + 2.0
        found = False
        while asyncio.get_event_loop().time() < deadline:
            if not bridge._response_queue.empty():
                item = bridge._response_queue.get_nowait()
                # Check command payload
                # 0x00 0x20 0x2C is standard header, command byte is 0x01
                assert item["cmd"] == 0x01
                assert item["payload"] == [0x02]
                found = True
                break
            await asyncio.sleep(0.05)

        assert (
            found
        ), "Client message was not received by FLStudioBridge response queue."

    # Disconnect the bridge
    bridge.disconnect()
    assert not bridge.connected
    assert not bridge.listening
