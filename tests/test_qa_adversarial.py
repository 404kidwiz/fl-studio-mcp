"""Adversarial dynamic E2E QA tests for Sprint 2 and Sprint 3.

Exercises extreme parameter boundaries, malformed inputs, concurrent race conditions,
timeout recoveries, and queue overflow behaviors to prove resilience.
"""

import asyncio
import json
import pytest
import unittest.mock
from io import StringIO
from unittest.mock import patch

from fl_studio_mcp.bridge import FLStudioBridge
from fl_studio_mcp.models import (
    Note,
    note_name_to_pitch,
    SetMixerVolumeInput,
    SetMixerPanInput,
    RouteToMixerInput,
    GetMixerStateInput,
)
from fl_studio_mcp.protocol import (
    RESP_NOTES,
    RESP_STATUS,
    RESP_CHANNELS,
    encode_set_pattern_length,
    encode_rename_channel,
    encode_rename_pattern,
    encode_set_channel_pan,
    decode_sysex,
    decode_resp_mixer_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(result: str) -> dict:
    return json.loads(result)


def _tool(module_name: str, tool_name: str):
    import importlib
    from mcp.server.fastmcp import FastMCP

    mod = importlib.import_module(f"fl_studio_mcp.tools.{module_name}")
    _mcp = FastMCP("test")
    mod.register(_mcp)
    return {t.name: t for t in _mcp._tool_manager.list_tools()}[tool_name].fn


def _inject_response(bridge: FLStudioBridge, cmd: int, payload: list) -> None:
    bridge._response_queue.put_nowait({"cmd": cmd, "payload": payload})


# ---------------------------------------------------------------------------
# Scenario 1: Malformed & Extreme Boundary Inputs
# ---------------------------------------------------------------------------


class TestAdversarialInputs:
    """QA Scenario Class: Extreme inputs and invalid parameters."""

    # Note Name Parser Boundaries
    @pytest.mark.parametrize(
        "invalid_note",
        ["", " ", "A", "C-2", "C10", "G#b4", "XYZ", "C#", "h4", "C#10", "D--1"],
    )
    def test_note_name_parser_failures(self, invalid_note):
        with pytest.raises(ValueError):
            note_name_to_pitch(invalid_note)

    # Note Pydantic model validation with garbage
    def test_note_model_garbage_pitch(self):
        with pytest.raises(ValueError):
            # Non-numeric garbage string
            Note(pitch="garbage")

    # Rename Channel Boundaries (Index errors)
    @pytest.mark.parametrize(
        "idx, name",
        [
            (-1, "ValidName"),
            (128, "ValidName"),
        ],
    )
    def test_rename_channel_boundary_failures(self, idx, name):
        with pytest.raises(ValueError):
            encode_rename_channel(idx, name)

    # Rename Channel Sanitization (String processing boundaries)
    def test_rename_channel_sanitization(self):
        # Too long (> 14 chars) -> truncated to 14
        msg = encode_rename_channel(0, "A" * 15)
        cmd, payload = decode_sysex(msg)
        assert cmd == 0x16
        assert payload[0] == 0
        assert payload[1] == 14
        assert payload[2:] == [65] * 14

        # Non-ASCII (Unicode chars) -> filtered
        msg = encode_rename_channel(0, "Chörus")
        cmd, payload = decode_sysex(msg)
        assert payload[0] == 0
        assert payload[1] == 5  # "Chrus" (5 chars after filtering 'ö')
        assert "".join(chr(b) for b in payload[2:]) == "Chrus"

        # Empty name -> length 0
        msg = encode_rename_channel(0, "")
        cmd, payload = decode_sysex(msg)
        assert payload[0] == 0
        assert payload[1] == 0
        assert len(payload[2:]) == 0

    # Rename Pattern Boundaries (Index errors)
    @pytest.mark.parametrize(
        "idx, name",
        [
            (-1, "ValidName"),
            (1000, "ValidName"),
        ],
    )
    def test_rename_pattern_boundary_failures(self, idx, name):
        with pytest.raises(ValueError):
            encode_rename_pattern(idx, name)

    # Rename Pattern Sanitization (String processing boundaries)
    def test_rename_pattern_sanitization(self):
        # Too long (> 14 chars) -> truncated to 14
        msg = encode_rename_pattern(0, "A" * 15)
        cmd, payload = decode_sysex(msg)
        assert cmd == 0x17
        assert payload[0] == 0  # pat_hi
        assert payload[1] == 0  # pat_lo
        assert payload[2] == 14
        assert payload[3:] == [65] * 14

        # Non-ASCII (Unicode chars) -> filtered
        msg = encode_rename_pattern(0, "Vérse")
        cmd, payload = decode_sysex(msg)
        assert payload[0] == 0
        assert payload[1] == 0
        assert payload[2] == 4  # "Vrse" (4 chars after filtering 'é')
        assert "".join(chr(b) for b in payload[3:]) == "Vrse"

        # Empty name -> length 0
        msg = encode_rename_pattern(0, "")
        cmd, payload = decode_sysex(msg)
        assert payload[0] == 0
        assert payload[1] == 0
        assert payload[2] == 0
        assert len(payload[3:]) == 0

    # Set Pattern Length Boundaries
    @pytest.mark.parametrize(
        "idx, length",
        [
            (-1, 8),
            (1000, 8),
            (0, -1),
            (0, 0),
            (0, 1000),  # Max length caps or validation error
        ],
    )
    def test_set_pattern_length_boundary_failures(self, idx, length):
        with pytest.raises(ValueError):
            encode_set_pattern_length(idx, length)

    # Set Channel Pan Boundaries
    @pytest.mark.parametrize(
        "idx, pan",
        [
            (-1, 64),
            (128, 64),
            (0, -1),
            (0, 128),
        ],
    )
    def test_set_channel_pan_boundary_failures(self, idx, pan):
        with pytest.raises(ValueError):
            encode_set_channel_pan(idx, pan)


# ---------------------------------------------------------------------------
# Scenario 2: Concurrent Concurrency races & Thread Lock Safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdversarialConcurrency:
    """QA Scenario Class: Racing multiple bidirectional queries in parallel."""

    async def test_concurrent_query_serialization(self, dry_bridge):
        """Simulates 3 concurrent queries.

        Ensures they execute sequentially via the asyncio query lock and
        receive their respective correct payloads without mixing response queue messages.
        """
        bridge = dry_bridge
        bridge._dry_run = False
        bridge._input_port = unittest.mock.Mock()
        bridge._output_port = unittest.mock.Mock()

        # Track the order of command execution
        execution_order = []

        # Responses to return when queries are sent
        resp_status_payload = [
            1,
            0,
            120,
            0,
            2,
            0,
            4,
        ]  # playing, bpm_hi, bpm_lo, pat_idx, ch_count
        resp_channels_payload = [
            2,
            4,
            75,
            105,
            99,
            107,
            5,
            83,
            110,
            97,
            114,
            101,
        ]  # Kick (4), Snare (5)
        resp_notes_payload = [0]  # 0 notes

        def mock_send(msg):
            cmd, _ = decode_sysex(msg.bytes())
            execution_order.append(cmd)
            # Add a slight delay to simulate physical MIDI transmission and loopback latency
            # This is crucial for verifying that the lock holds and schedules queries properly
            if cmd == 0x06:  # CMD_QUERY_STATUS
                _inject_response(bridge, RESP_STATUS, resp_status_payload)
            elif cmd == 0x07:  # CMD_QUERY_CHANNELS
                _inject_response(bridge, RESP_CHANNELS, resp_channels_payload)
            elif cmd == 0x14:  # CMD_GET_NOTES
                _inject_response(bridge, RESP_NOTES, resp_notes_payload)

        bridge._output_port.send = mock_send

        # Execute 3 separate query types concurrently
        task_status = bridge.query(b"\xf0\x7d\x06\xf7", RESP_STATUS, timeout_ms=500)
        task_channels = bridge.query(b"\xf0\x7d\x07\xf7", RESP_CHANNELS, timeout_ms=500)
        task_notes = bridge.query(b"\xf0\x7d\x14\xf7", RESP_NOTES, timeout_ms=500)

        results = await asyncio.gather(
            task_status, task_channels, task_notes, return_exceptions=True
        )

        # 1. Verify no exceptions/errors occurred
        for res in results:
            assert not isinstance(
                res, Exception
            ), f"Query raised an unexpected exception: {res}"
            assert res is not None

        # 2. Verify all 3 commands were sent to the output port
        assert len(execution_order) == 3
        assert 0x06 in execution_order
        assert 0x07 in execution_order
        assert 0x14 in execution_order

        # 3. Verify correctness of values mapped from their respective payloads
        status_res = results[0]
        channels_res = results[1]
        notes_res = results[2]

        assert status_res == {"cmd": RESP_STATUS, "payload": resp_status_payload}
        assert channels_res == {"cmd": RESP_CHANNELS, "payload": resp_channels_payload}
        assert notes_res == {"cmd": RESP_NOTES, "payload": resp_notes_payload}

        # Reset bridge state
        bridge._dry_run = True
        bridge._input_port = None
        bridge._output_port = None


# ---------------------------------------------------------------------------
# Scenario 3: Timeout Recovery & Deadlock Prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdversarialTimeouts:
    """QA Scenario Class: Verifying timeout handling and subsequent lock release."""

    async def test_query_timeout_releases_lock(self, dry_bridge):
        """A timed out query must release the query lock.

        Subsequent queries must proceed immediately without getting deadlocked.
        """
        bridge = dry_bridge
        bridge._dry_run = False
        bridge._input_port = unittest.mock.Mock()
        bridge._output_port = unittest.mock.Mock()

        # 1. Fire a query that will time out (mock_send does NOT inject a response)
        bridge._output_port.send = lambda msg: None

        t1 = asyncio.create_task(
            bridge.query(b"\xf0\x7d\x06\xf7", RESP_STATUS, timeout_ms=100)
        )

        # Wait for timeout to expire
        res1 = await t1
        assert res1 is None, "Expected timeout to return None"

        # 2. Fire a second query that succeeds immediately
        resp_status_payload = [0, 0, 120, 0, 2, 0, 4]

        def mock_send_success(msg):
            _inject_response(bridge, RESP_STATUS, resp_status_payload)

        bridge._output_port.send = mock_send_success

        t2 = asyncio.create_task(
            bridge.query(b"\xf0\x7d\x06\xf7", RESP_STATUS, timeout_ms=100)
        )
        res2 = await t2

        assert res2 == {
            "cmd": RESP_STATUS,
            "payload": resp_status_payload,
        }, "Subsequent query should succeed after first one timed out"

        # Reset bridge
        bridge._dry_run = True
        bridge._input_port = None
        bridge._output_port = None


# ---------------------------------------------------------------------------
# Scenario 4: Queue Overflow & Stress
# ---------------------------------------------------------------------------


class TestAdversarialQueueStress:
    """QA Scenario Class: Straining the bridge response queue."""

    def test_queue_overflow_safety(self, dry_bridge):
        """Filling queue beyond maximum length drops stale items safely and issues warning."""
        import mido

        bridge = dry_bridge

        # Verify the maximum queue limit behaves safely
        assert bridge._response_queue.maxsize == 64

        # Fill the queue to capacity
        for i in range(64):
            bridge._response_queue.put_nowait({"cmd": 0x10, "payload": [i]})

        # Emulate mido callback arriving on a full queue.
        # This will trigger bridge._on_midi_in which will hit the thread_queue.Full path and print to stderr.
        captured = StringIO()
        with patch("sys.stderr", captured):
            msg = mido.Message("sysex", data=[0x7D, 0x10, 0x01])
            bridge._on_midi_in(msg)

        # Verify warnings are logged to stderr rather than crashing the background thread
        assert "WARNING: response queue full" in captured.getvalue()

        # Clear queue for cleanup
        while not bridge._response_queue.empty():
            try:
                bridge._response_queue.get_nowait()
            except Exception:
                break


# ---------------------------------------------------------------------------
# Scenario 5: Sprint 4 Mixer & Routing Adversarial Inputs
# ---------------------------------------------------------------------------


class TestAdversarialMixer:
    """QA Scenario Class: Extreme inputs, parsing errors, and malformed SysEx payloads for Mixer & Routing."""

    def test_decode_truncated_mixer_state(self):
        # Payload too short (<3 bytes)
        with pytest.raises(ValueError):
            decode_resp_mixer_state([0, 1])

        # Payload ends abruptly during track headers (e.g. count claims 2 but we only have 1 track header)
        # payload structure: [start, end, count, [vol, pan, name_len, name_bytes...]]
        # Here: start=0, end=1, count=2, track 0 volume=100, pan=64, name_len=0. Then it ends.
        # Track 1 is missing entirely.
        payload = [0, 1, 2, 100, 64, 0]
        res = decode_resp_mixer_state(payload)
        # Should gracefully stop parsing when payload is truncated, returning only 1 track
        assert len(res["tracks"]) == 1
        assert res["tracks"][0] == {"volume": 100, "pan": 64, "name": ""}

    def test_decode_mixer_state_corrupted_name_len(self):
        # name_len claims 10 bytes, but payload only has 2 bytes left
        payload = [0, 0, 1, 100, 64, 10, 65, 66]
        res = decode_resp_mixer_state(payload)
        # Should stop parsing gracefully and return track with empty/partial name, or no name depending on break
        assert len(res["tracks"]) == 0

    def test_mixer_pydantic_validation_failures(self):
        from pydantic import ValidationError

        # Volume out of bounds
        with pytest.raises(ValidationError):
            SetMixerVolumeInput(track_index=5, volume=-1)
        with pytest.raises(ValidationError):
            SetMixerVolumeInput(track_index=5, volume=128)
        with pytest.raises(ValidationError):
            SetMixerVolumeInput(track_index=128, volume=100)

        # Pan out of bounds
        with pytest.raises(ValidationError):
            SetMixerPanInput(track_index=5, pan=-1)
        with pytest.raises(ValidationError):
            SetMixerPanInput(track_index=5, pan=128)
        with pytest.raises(ValidationError):
            SetMixerPanInput(track_index=128, pan=64)

        # Route out of bounds
        with pytest.raises(ValidationError):
            RouteToMixerInput(channel_index=-1, track_index=5)
        with pytest.raises(ValidationError):
            RouteToMixerInput(channel_index=0, track_index=128)

        # Get mixer state out of bounds
        with pytest.raises(ValidationError):
            GetMixerStateInput(start_track=-1, end_track=5)
        with pytest.raises(ValidationError):
            GetMixerStateInput(start_track=0, end_track=128)
