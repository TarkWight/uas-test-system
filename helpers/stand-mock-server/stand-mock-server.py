import asyncio
import argparse
import struct
import time
from dataclasses import dataclass

HOST = "127.0.0.1"
AXIS0_PORT = 12540 
AXIS1_PORT = 12520


def f32(data: bytes) -> float:
    return struct.unpack("<f", data)[0]


def pack_f32(value: float) -> bytes:
    return struct.pack("<f", float(value))


def move_towards(current: float, target: float, max_delta: float) -> float:
    delta = target - current
    if abs(delta) <= max_delta:
        return target
    return current + max_delta * (1 if delta > 0 else -1)


@dataclass
class ControlPacket:
    raw: bytes
    field0: int
    field1: int
    length: int
    position: float
    velocity: float
    torque: float
    flags: tuple[int, int, int, int]
    crc: bytes

    @classmethod
    def parse(cls, data: bytes) -> "ControlPacket":
        if len(data) < 22:
            raise ValueError(f"short packet: {len(data)} bytes")

        data = data[:22]
        return cls(
            raw=data,
            field0=data[0],
            field1=data[1],
            length=int.from_bytes(data[2:4], "big"),
            position=f32(data[4:8]),
            velocity=f32(data[8:12]),
            torque=f32(data[12:16]),
            flags=(data[16], data[17], data[18], data[19]),
            crc=data[20:22],
        )


class AxisMock:
    def __init__(
        self,
        name: str,
        channel_id: int,
        initial_position: float = 0.0,
        max_speed_deg_s: float = 180.0,
    ):
        self.name = name
        self.channel_id = channel_id  # 0x03 для Y, 0x04 для Z по сниффу
        self.position = initial_position
        self.target_position = initial_position
        self.velocity_cmd = 0.0
        self.torque_cmd = 0.0
        self.flags = (0, 0, 0, 0)
        self.voltage = 28.3
        self.ibus = 0.0
        self.max_speed_deg_s = max_speed_deg_s
        self.last_update = time.monotonic()

    def apply_command(self, packet: ControlPacket) -> None:
        self.target_position = packet.position
        self.velocity_cmd = packet.velocity
        self.torque_cmd = packet.torque
        self.flags = packet.flags

    def update_physics(self) -> None:
        now = time.monotonic()
        dt = now - self.last_update
        self.last_update = now

        max_delta = self.max_speed_deg_s * dt
        self.position = move_towards(
            self.position,
            self.target_position,
            max_delta,
        )

        # Условная имитация тока: чем дальше до цели, тем выше ток.
        error = abs(self.target_position - self.position)
        self.ibus = min(5.0, error / 30.0)

    def telemetry_frame(self) -> bytes:
        self.update_physics()

        frame = bytearray(30)

        # По pcap: ответы стенда имеют вид 03/04 02 00 1C + 24 байта float + 00 00
        frame[0] = self.channel_id
        frame[1] = 0x02
        frame[2:4] = bytes([0x00, 0x1C])

        frame[4:8] = pack_f32(self.position)
        frame[8:12] = pack_f32(self.target_position)
        frame[12:16] = pack_f32(self.torque_cmd)
        frame[16:20] = pack_f32(0.0)          # SetTorque / резерв
        frame[20:24] = pack_f32(self.voltage)
        frame[24:28] = pack_f32(self.ibus)
        frame[28:30] = bytes([0x00, 0x00])   # хвостовое поле / CRC-заглушка

        return bytes(frame)

    def log_command(self, packet: ControlPacket) -> None:
        hex_raw = packet.raw.hex(" ").upper()
        print(
            f"\n[{self.name}] RX {len(packet.raw)} bytes: {hex_raw}\n"
            f"  header     = 0x{packet.field0:02X} 0x{packet.field1:02X}\n"
            f"  length     = {packet.length}\n"
            f"  position   = {packet.position:.3f}\n"
            f"  velocity   = {packet.velocity:.3f}\n"
            f"  torque     = {packet.torque:.3f}\n"
            f"  flags      = {packet.flags}\n"
            f"  crc/tail   = {packet.crc.hex(' ').upper()}\n"
            f"  target now = {self.target_position:.3f}, current = {self.position:.3f}"
        )


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    axis: AxisMock,
):
    peer = writer.get_extra_info("peername")
    print(f"[{axis.name}] client connected: {peer}")

    buffer = bytearray()

    try:
        while True:
            chunk = await reader.read(1024)
            if not chunk:
                break

            buffer.extend(chunk)

            while len(buffer) >= 22:
                raw_packet = bytes(buffer[:22])
                del buffer[:22]

                try:
                    packet = ControlPacket.parse(raw_packet)
                except ValueError as exc:
                    print(f"[{axis.name}] bad packet: {exc}")
                    continue

                axis.apply_command(packet)
                axis.log_command(packet)

                response = axis.telemetry_frame()
                writer.write(response)
                await writer.drain()

                vals = struct.unpack("<ffffff", response[4:28])
                print(
                    f"[{axis.name}] TX 30 bytes: "
                    f"pos={vals[0]:.3f}, setPos={vals[1]:.3f}, "
                    f"torque={vals[2]:.3f}, setTorque={vals[3]:.3f}, "
                    f"voltage={vals[4]:.3f}, ibus={vals[5]:.3f}"
                )

    except ConnectionResetError:
        pass
    finally:
        print(f"[{axis.name}] client disconnected")
        writer.close()
        await writer.wait_closed()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--axis0-port", type=int, default=AXIS0_PORT)
    parser.add_argument("--axis1-port", type=int, default=AXIS1_PORT)
    parser.add_argument("--speed", type=float, default=180.0, help="deg/s")
    args = parser.parse_args()

    axis0 = AxisMock("Y / axis0", channel_id=0x03, max_speed_deg_s=args.speed)
    axis1 = AxisMock("Z / axis1", channel_id=0x04, max_speed_deg_s=args.speed)

    server0 = await asyncio.start_server(
        lambda r, w: handle_client(r, w, axis0),
        args.host,
        args.axis0_port,
    )

    server1 = await asyncio.start_server(
        lambda r, w: handle_client(r, w, axis1),
        args.host,
        args.axis1_port,
    )

    print(f"AXIS0 mock listening on {args.host}:{args.axis0_port}")
    print(f"AXIS1 mock listening on {args.host}:{args.axis1_port}")
    print("Press Ctrl+C to stop.")

    async with server0, server1:
        await asyncio.gather(
            server0.serve_forever(),
            server1.serve_forever(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")