import argparse
import asyncio
import csv
import itertools
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


MOCK_ROUTES = [
    {"name": "axis0", "listen_host": "127.0.0.1", "listen_port": 11540, "stand_host": "127.0.0.1", "stand_port": 12540},
    {"name": "axis1", "listen_host": "127.0.0.1", "listen_port": 11520, "stand_host": "127.0.0.1", "stand_port": 12520},
]

REAL_ROUTES = [
    {"name": "axis0", "listen_host": "127.0.0.1", "listen_port": 11540, "stand_host": "192.168.1.100", "stand_port": 11540},
    {"name": "axis1", "listen_host": "127.0.0.1", "listen_port": 11520, "stand_host": "192.168.1.101", "stand_port": 11520},
]


SESSION_DIR: Path
TEXT_LOG: Path
PACKETS_CSV: Path
EVENTS_CSV: Path
SUMMARY_CSV: Path

CONNECTION_IDS = itertools.count(1)
PACKET_SEQ = itertools.count(1)


@dataclass
class DirectionStats:
    chunks: int = 0
    frames: int = 0
    bytes_total: int = 0
    first_mono: float | None = None
    last_mono: float | None = None
    last_frame_mono: float | None = None
    min_frame_delta_ms: float | None = None
    max_frame_delta_ms: float | None = None
    sum_frame_delta_ms: float = 0.0
    frame_delta_count: int = 0


@dataclass
class ConnectionStats:
    route: str
    connection_id: int
    created_mono: float = field(default_factory=time.monotonic)
    closed_mono: float | None = None
    app_to_stand: DirectionStats = field(default_factory=DirectionStats)
    stand_to_app: DirectionStats = field(default_factory=DirectionStats)
    request_times: list[float] = field(default_factory=list)
    response_times: list[float] = field(default_factory=list)


CONNECTION_STATS: dict[int, ConnectionStats] = {}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def f32(data: bytes) -> float:
    return struct.unpack("<f", data)[0]


def ms(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def write_line(text: str):
    print(text)
    with TEXT_LOG.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def csv_append(path: Path, row: list):
    with path.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(row)


def init_files():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    with PACKETS_CSV.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([
            "time", "seq", "connection_id", "route", "direction", "record_type",
            "chunk_size", "frame_size", "frame_index_in_chunk",
            "packet_kind",
            "delta_ms_direction",
            "delta_ms_connection",
            "delta_ms_same_packet_type",
            "latency_ms_request_to_response",
            "header0", "header1", "length",
            "position", "set_position_or_velocity", "torque",
            "set_torque_or_flags", "voltage", "current", "crc_or_tail",
            "hex",
        ])

    with EVENTS_CSV.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([
            "time", "connection_id", "route", "event", "details",
        ])

    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([
            "time", "connection_id", "route", "duration_ms",
            "app_to_stand_bytes", "app_to_stand_chunks", "app_to_stand_frames",
            "stand_to_app_bytes", "stand_to_app_chunks", "stand_to_app_frames",
            "request_count", "response_count",
            "avg_request_period_ms",
            "min_request_period_ms",
            "max_request_period_ms",
            "avg_response_latency_ms",
            "min_response_latency_ms",
            "max_response_latency_ms",
        ])


def event(connection_id: int | str, route_name: str, event_name: str, details: str = ""):
    msg = f"[{now_text()}] [{route_name}] [{connection_id}] {event_name}"
    if details:
        msg += f": {details}"
    write_line(msg)
    csv_append(EVENTS_CSV, [now_text(), connection_id, route_name, event_name, details])


def parse_request(data: bytes) -> dict | None:
    if len(data) != 22:
        return None

    flags = data[16:20]
    return {
        "packet_kind": "request_22",
        "header0": f"0x{data[0]:02X}",
        "header1": f"0x{data[1]:02X}",
        "length": int.from_bytes(data[2:4], "big"),
        "position": f"{f32(data[4:8]):.6f}",
        "set_position_or_velocity": f"{f32(data[8:12]):.6f}",
        "torque": f"{f32(data[12:16]):.6f}",
        "set_torque_or_flags": f"{flags[0]},{flags[1]},{flags[2]},{flags[3]}",
        "voltage": "",
        "current": "",
        "crc_or_tail": data[20:22].hex(" ").upper(),
    }


def parse_response(data: bytes) -> dict | None:
    if len(data) != 30:
        return None

    return {
        "packet_kind": "response_30",
        "header0": f"0x{data[0]:02X}",
        "header1": f"0x{data[1]:02X}",
        "length": int.from_bytes(data[2:4], "big"),
        "position": f"{f32(data[4:8]):.6f}",
        "set_position_or_velocity": f"{f32(data[8:12]):.6f}",
        "torque": f"{f32(data[12:16]):.6f}",
        "set_torque_or_flags": f"{f32(data[16:20]):.6f}",
        "voltage": f"{f32(data[20:24]):.6f}",
        "current": f"{f32(data[24:28]):.6f}",
        "crc_or_tail": data[28:30].hex(" ").upper(),
    }


def parse_frame(direction: str, frame: bytes) -> dict | None:
    if direction == "app_to_stand":
        return parse_request(frame)
    if direction == "stand_to_app":
        return parse_response(frame)
    return None


def expected_frame_size(direction: str) -> int:
    return 22 if direction == "app_to_stand" else 30


def append_raw(route_name: str, connection_id: int, direction: str, data: bytes):
    path = SESSION_DIR / f"{route_name}_{connection_id}_{direction}.bin"
    with path.open("ab") as f:
        f.write(data)


def get_direction_stats(stats: ConnectionStats, direction: str) -> DirectionStats:
    return stats.app_to_stand if direction == "app_to_stand" else stats.stand_to_app


def update_chunk_stats(connection_id: int, direction: str, data_size: int, mono: float):
    stats = CONNECTION_STATS[connection_id]
    ds = get_direction_stats(stats, direction)

    ds.chunks += 1
    ds.bytes_total += data_size
    if ds.first_mono is None:
        ds.first_mono = mono
    ds.last_mono = mono


def update_frame_stats(connection_id: int, direction: str, mono: float) -> tuple[float | None, float | None, float | None, float | None]:
    stats = CONNECTION_STATS[connection_id]
    ds = get_direction_stats(stats, direction)

    delta_direction_ms = None
    if ds.last_frame_mono is not None:
        delta_direction_ms = (mono - ds.last_frame_mono) * 1000.0
        ds.frame_delta_count += 1
        ds.sum_frame_delta_ms += delta_direction_ms
        ds.min_frame_delta_ms = delta_direction_ms if ds.min_frame_delta_ms is None else min(ds.min_frame_delta_ms, delta_direction_ms)
        ds.max_frame_delta_ms = delta_direction_ms if ds.max_frame_delta_ms is None else max(ds.max_frame_delta_ms, delta_direction_ms)

    ds.last_frame_mono = mono
    ds.frames += 1

    delta_connection_ms = (mono - stats.created_mono) * 1000.0

    delta_same_type_ms = None
    latency_ms = None

    if direction == "app_to_stand":
        if stats.request_times:
            delta_same_type_ms = (mono - stats.request_times[-1]) * 1000.0
        stats.request_times.append(mono)
    else:
        if stats.response_times:
            delta_same_type_ms = (mono - stats.response_times[-1]) * 1000.0
        stats.response_times.append(mono)

        if stats.request_times:
            request_time = stats.request_times[min(len(stats.response_times) - 1, len(stats.request_times) - 1)]
            latency_ms = (mono - request_time) * 1000.0

    return delta_direction_ms, delta_connection_ms, delta_same_type_ms, latency_ms


def append_packet_csv(
    connection_id: int,
    route_name: str,
    direction: str,
    record_type: str,
    chunk_size: int,
    frame: bytes,
    frame_index: int,
    parsed: dict | None,
    delta_direction_ms: float | None = None,
    delta_connection_ms: float | None = None,
    delta_same_type_ms: float | None = None,
    latency_ms: float | None = None,
):
    parsed = parsed or {}
    csv_append(PACKETS_CSV, [
        now_text(),
        next(PACKET_SEQ),
        connection_id,
        route_name,
        direction,
        record_type,
        chunk_size,
        len(frame),
        frame_index,
        parsed.get("packet_kind", "unknown_or_partial"),
        ms(delta_direction_ms),
        ms(delta_connection_ms),
        ms(delta_same_type_ms),
        ms(latency_ms),
        parsed.get("header0", ""),
        parsed.get("header1", ""),
        parsed.get("length", ""),
        parsed.get("position", ""),
        parsed.get("set_position_or_velocity", ""),
        parsed.get("torque", ""),
        parsed.get("set_torque_or_flags", ""),
        parsed.get("voltage", ""),
        parsed.get("current", ""),
        parsed.get("crc_or_tail", ""),
        hex_dump(frame),
    ])


def log_frame(connection_id: int, route_name: str, direction: str, frame: bytes, frame_index: int, chunk_size: int):
    mono = time.monotonic()
    parsed = parse_frame(direction, frame)
    delta_direction_ms, delta_connection_ms, delta_same_type_ms, latency_ms = update_frame_stats(connection_id, direction, mono)

    write_line(
        f"[{now_text()}] [{route_name}] [{connection_id}] {direction} "
        f"frame#{frame_index} {len(frame)} bytes "
        f"delta_dir={ms(delta_direction_ms)}ms "
        f"delta_conn={ms(delta_connection_ms)}ms "
        f"delta_same={ms(delta_same_type_ms)}ms "
        f"latency={ms(latency_ms)}ms"
    )
    write_line(f"  {hex_dump(frame)}")

    if parsed:
        write_line(
            "  decoded: "
            f"h={parsed['header0']} {parsed['header1']}, "
            f"len={parsed['length']}, "
            f"pos={parsed['position']}, "
            f"v/setPos={parsed['set_position_or_velocity']}, "
            f"torque={parsed['torque']}, "
            f"setTorque/flags={parsed['set_torque_or_flags']}, "
            f"voltage={parsed['voltage']}, "
            f"current={parsed['current']}, "
            f"tail={parsed['crc_or_tail']}"
        )
    else:
        write_line("  decoded: <not decoded>")

    write_line("")
    append_packet_csv(
        connection_id,
        route_name,
        direction,
        "frame",
        chunk_size,
        frame,
        frame_index,
        parsed,
        delta_direction_ms,
        delta_connection_ms,
        delta_same_type_ms,
        latency_ms,
    )


class DirectionFrameLogger:
    def __init__(self, connection_id: int, route_name: str, direction: str):
        self.connection_id = connection_id
        self.route_name = route_name
        self.direction = direction
        self.buffer = bytearray()
        self.frame_size = expected_frame_size(direction)

    def feed(self, data: bytes):
        self.buffer.extend(data)

        frame_index = 0
        while len(self.buffer) >= self.frame_size:
            frame = bytes(self.buffer[:self.frame_size])
            del self.buffer[:self.frame_size]
            log_frame(self.connection_id, self.route_name, self.direction, frame, frame_index, len(data))
            frame_index += 1

    def flush_partial(self):
        if not self.buffer:
            return

        partial = bytes(self.buffer)
        self.buffer.clear()

        event(
            self.connection_id,
            self.route_name,
            f"partial_frame_left_{self.direction}",
            f"{len(partial)} bytes: {hex_dump(partial)}",
        )

        append_packet_csv(
            self.connection_id,
            self.route_name,
            self.direction,
            "partial_left",
            len(partial),
            partial,
            0,
            None,
        )


@dataclass
class PipeResult:
    direction: str
    reason: str
    total_bytes: int


async def pipe(reader, writer, connection_id: int, route_name: str, direction: str) -> PipeResult:
    total = 0
    frame_logger = DirectionFrameLogger(connection_id, route_name, direction)

    try:
        event(connection_id, route_name, f"pipe_started_{direction}")

        while True:
            data = await reader.read(4096)

            if not data:
                event(connection_id, route_name, f"EOF_{direction}", f"total={total}")
                return PipeResult(direction, "eof", total)

            mono = time.monotonic()
            total += len(data)
            update_chunk_stats(connection_id, direction, len(data), mono)

            write_line(f"[{now_text()}] [{route_name}] [{connection_id}] {direction} chunk {len(data)} bytes")
            write_line(f"  {hex_dump(data)}")
            write_line("")

            append_raw(route_name, connection_id, direction, data)
            append_packet_csv(connection_id, route_name, direction, "chunk", len(data), data, -1, None)
            frame_logger.feed(data)

            try:
                writer.write(data)
                await writer.drain()
            except ConnectionResetError as e:
                event(connection_id, route_name, f"write_reset_{direction}", repr(e))
                return PipeResult(direction, "write_reset", total)
            except BrokenPipeError as e:
                event(connection_id, route_name, f"broken_pipe_{direction}", repr(e))
                return PipeResult(direction, "broken_pipe", total)
            except OSError as e:
                event(connection_id, route_name, f"write_error_{direction}", repr(e))
                return PipeResult(direction, "write_error", total)

    except ConnectionResetError as e:
        event(connection_id, route_name, f"read_reset_{direction}", repr(e))
        return PipeResult(direction, "read_reset", total)
    except asyncio.CancelledError:
        event(connection_id, route_name, f"pipe_cancelled_{direction}", f"total={total}")
        raise
    except OSError as e:
        event(connection_id, route_name, f"read_error_{direction}", repr(e))
        return PipeResult(direction, "read_error", total)
    finally:
        frame_logger.flush_partial()
        event(connection_id, route_name, f"pipe_closing_{direction}", f"total={total}")

        writer.close()
        try:
            await writer.wait_closed()
        except Exception as e:
            event(connection_id, route_name, f"wait_closed_error_{direction}", repr(e))


def socket_info(writer) -> str:
    sock = writer.get_extra_info("socket")
    peer = writer.get_extra_info("peername")
    local = writer.get_extra_info("sockname")

    parts = [f"local={local}", f"peer={peer}"]

    if sock is not None:
        try:
            parts.append(f"fileno={sock.fileno()}")
            parts.append(f"family={sock.family}")
            parts.append(f"type={sock.type}")
            parts.append(f"proto={sock.proto}")
        except Exception:
            pass

    return ", ".join(parts)


def periods_ms(times: list[float]) -> list[float]:
    return [(times[i] - times[i - 1]) * 1000.0 for i in range(1, len(times))]


def pair_latencies_ms(requests: list[float], responses: list[float]) -> list[float]:
    return [(responses[i] - requests[i]) * 1000.0 for i in range(min(len(requests), len(responses)))]


def avg(values: list[float]) -> str:
    return "" if not values else f"{sum(values) / len(values):.3f}"


def min_s(values: list[float]) -> str:
    return "" if not values else f"{min(values):.3f}"


def max_s(values: list[float]) -> str:
    return "" if not values else f"{max(values):.3f}"


def write_summary(connection_id: int):
    stats = CONNECTION_STATS.get(connection_id)
    if not stats:
        return

    stats.closed_mono = time.monotonic()

    request_periods = periods_ms(stats.request_times)
    response_latencies = pair_latencies_ms(stats.request_times, stats.response_times)
    duration_ms = (stats.closed_mono - stats.created_mono) * 1000.0

    csv_append(SUMMARY_CSV, [
        now_text(),
        connection_id,
        stats.route,
        f"{duration_ms:.3f}",
        stats.app_to_stand.bytes_total,
        stats.app_to_stand.chunks,
        stats.app_to_stand.frames,
        stats.stand_to_app.bytes_total,
        stats.stand_to_app.chunks,
        stats.stand_to_app.frames,
        len(stats.request_times),
        len(stats.response_times),
        avg(request_periods),
        min_s(request_periods),
        max_s(request_periods),
        avg(response_latencies),
        min_s(response_latencies),
        max_s(response_latencies),
    ])

    event(
        connection_id,
        stats.route,
        "summary",
        (
            f"duration_ms={duration_ms:.3f}, "
            f"requests={len(stats.request_times)}, "
            f"responses={len(stats.response_times)}, "
            f"avg_request_period_ms={avg(request_periods)}, "
            f"avg_response_latency_ms={avg(response_latencies)}"
        ),
    )


async def handle_client(client_reader, client_writer, route):
    connection_id = next(CONNECTION_IDS)
    route_name = route["name"]
    CONNECTION_STATS[connection_id] = ConnectionStats(route=route_name, connection_id=connection_id)

    event(connection_id, route_name, "app_connected", socket_info(client_writer))

    try:
        event(connection_id, route_name, "stand_connecting", f"{route['stand_host']}:{route['stand_port']}")

        stand_reader, stand_writer = await asyncio.open_connection(
            route["stand_host"],
            route["stand_port"],
        )
    except OSError as e:
        event(connection_id, route_name, "stand_connect_failed", repr(e))
        client_writer.close()
        await client_writer.wait_closed()
        write_summary(connection_id)
        return

    event(connection_id, route_name, "stand_connected", socket_info(stand_writer))

    app_to_stand = asyncio.create_task(pipe(client_reader, stand_writer, connection_id, route_name, "app_to_stand"))
    stand_to_app = asyncio.create_task(pipe(stand_reader, client_writer, connection_id, route_name, "stand_to_app"))

    done, pending = await asyncio.wait(
        {app_to_stand, stand_to_app},
        return_when=asyncio.FIRST_COMPLETED,
    )

    first_results = await asyncio.gather(*done, return_exceptions=True)
    for result in first_results:
        if isinstance(result, PipeResult):
            event(
                connection_id,
                route_name,
                "first_finished",
                f"direction={result.direction}, reason={result.reason}, total={result.total_bytes}",
            )
        else:
            event(connection_id, route_name, "first_finished_exception", repr(result))

    for task in pending:
        task.cancel()

    rest_results = await asyncio.gather(*pending, return_exceptions=True)
    for result in rest_results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            event(connection_id, route_name, "pending_task_exception", repr(result))

    event(connection_id, route_name, "connection_closed")
    write_summary(connection_id)


async def marker_console():
    event("-", "user", "marker_console_started", "type text and press Enter; use q to stop proxy")

    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            return

        text = line.strip()
        if not text:
            continue

        if text.lower() in {"q", "quit", "exit"}:
            event("-", "user", "quit_requested", text)
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()
            return

        event("-", "user", "MARK", text)


async def start_route(route):
    try:
        server = await asyncio.start_server(
            lambda r, w: handle_client(r, w, route),
            route["listen_host"],
            route["listen_port"],
            reuse_address=True,
        )
    except OSError as e:
        event("-", route["name"], "listen_failed", f"{route['listen_host']}:{route['listen_port']}: {repr(e)}")
        raise

    event(
        "-",
        route["name"],
        "listening",
        f"{route['listen_host']}:{route['listen_port']} -> {route['stand_host']}:{route['stand_port']}",
    )

    async with server:
        await server.serve_forever()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["mock", "real"], default="mock")
    parser.add_argument("--no-markers", action="store_true")
    args = parser.parse_args()

    routes = MOCK_ROUTES if args.target == "mock" else REAL_ROUTES

    global SESSION_DIR, TEXT_LOG, PACKETS_CSV, EVENTS_CSV, SUMMARY_CSV
    SESSION_DIR = Path("proxy_logs") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.target}"
    TEXT_LOG = SESSION_DIR / "proxy.log"
    PACKETS_CSV = SESSION_DIR / "packets.csv"
    EVENTS_CSV = SESSION_DIR / "events.csv"
    SUMMARY_CSV = SESSION_DIR / "summary.csv"

    init_files()

    event("-", "proxy", "session_dir", str(SESSION_DIR.resolve()))
    event("-", "proxy", "target", args.target)

    tasks = [asyncio.create_task(start_route(route)) for route in routes]

    if not args.no_markers:
        tasks.append(asyncio.create_task(marker_console()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        write_line("")
        write_line("[i] stopped by user")