"""Send the encrypted vault to another device on the same network.

The pairing code is checked before any bytes are sent. The passphrase is not
part of this exchange. The offer stops when the window closes.
"""

from __future__ import annotations

import hmac
import secrets
import select
import socket
import threading
import time

MAGIC = b"LPS1"
CODE_LENGTH = 6
UDP_PORT = 39221
MAX_VAULT_BYTES = 1_048_576
OFFER_SECONDS = 120
_HANDSHAKE = 4 + CODE_LENGTH


def new_pairing_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(CODE_LENGTH))


def normalize_code(code: str) -> str:
    digits = "".join(character for character in code if character.isdigit())
    if len(digits) != CODE_LENGTH:
        raise ValueError("The pairing code is 6 digits.")
    return digits


def lan_addresses() -> list[str]:
    """IPv4 addresses another device on this network can use."""
    found: list[str] = []
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = probe.getsockname()[0]
    except OSError:
        address = ""
    finally:
        probe.close()
    if address and not address.startswith("127."):
        found.append(address)
    return found


def _read_exact(connection: socket.socket, size: int) -> bytes | None:
    buffer = bytearray()
    while len(buffer) < size:
        try:
            chunk = connection.recv(size - len(buffer))
        except socket.timeout:
            return None
        if not chunk:
            return None
        buffer.extend(chunk)
    return bytes(buffer)


def _split_address(address: str) -> tuple[str, int]:
    text = address.strip()
    if ":" not in text:
        raise ValueError("The other device's address needs a port, such as 192.168.1.20:12345.")
    host, port_text = text.rsplit(":", 1)
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("The other device's address needs a port, such as 192.168.1.20:12345.") from exc
    if not host or port < 1 or port > 65535:
        raise ValueError("The other device's address needs a port, such as 192.168.1.20:12345.")
    return host, port


class VaultOffer:
    """Share one vault until another device presents the pairing code."""

    def __init__(self, payload: bytes, code: str | None = None) -> None:
        if not payload.startswith(b"LPV") or len(payload) > MAX_VAULT_BYTES:
            raise ValueError("The saved password file is damaged.")
        self.payload = payload
        self.code = normalize_code(code) if code is not None else new_pairing_code()
        self.port = 0
        self.addresses = lan_addresses()
        self.sent = False
        self.error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._tcp: socket.socket | None = None
        self._udp: socket.socket | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._serve, name="vault-offer", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 2
        while self.port == 0 and not self.error and time.monotonic() < deadline:
            time.sleep(0.01)
        if self.port == 0 and not self.error:
            self.error = "Could not offer the vault on this network."

    def stop(self) -> None:
        self._stop.set()
        for held in (self._tcp, self._udp):
            if held is not None:
                try:
                    held.close()
                except OSError:
                    pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def where(self) -> str:
        if self.addresses:
            return ", ".join(f"{ip}:{self.port}" for ip in self.addresses)
        if self.port:
            return f"port {self.port}"
        return ""

    def _serve(self) -> None:
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            tcp.bind(("0.0.0.0", 0))
            tcp.listen(1)
            tcp.setblocking(False)
            self._tcp = tcp
            self.port = int(tcp.getsockname()[1])
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind(("0.0.0.0", 0))
            self._udp = udp
            deadline = time.monotonic() + OFFER_SECONDS
            next_beacon = 0.0
            while not self._stop.is_set() and time.monotonic() < deadline and not self.sent:
                now = time.monotonic()
                if now >= next_beacon:
                    self._beacon()
                    next_beacon = now + 0.4
                try:
                    readable, _, _ = select.select([tcp], [], [], 0.2)
                except OSError:
                    break
                if not readable:
                    continue
                try:
                    connection, _address = tcp.accept()
                except OSError:
                    break
                try:
                    self._handle(connection)
                finally:
                    connection.close()
        except OSError:
            if not self._stop.is_set():
                self.error = "Could not offer the vault on this network."
        finally:
            try:
                tcp.close()
            except OSError:
                pass
            if self._udp is not None:
                try:
                    self._udp.close()
                except OSError:
                    pass

    def _beacon(self) -> None:
        if self._udp is None or self.port == 0:
            return
        packet = MAGIC + self.port.to_bytes(2, "big")
        try:
            self._udp.sendto(packet, ("255.255.255.255", UDP_PORT))
        except OSError:
            pass

    def _handle(self, connection: socket.socket) -> None:
        connection.settimeout(5)
        data = _read_exact(connection, _HANDSHAKE)
        if data is None or data[:4] != MAGIC:
            connection.sendall(b"NO")
            return
        presented = data[4:].decode("ascii", "replace")
        if not hmac.compare_digest(presented, self.code):
            connection.sendall(b"NO")
            return
        connection.sendall(b"OK" + len(self.payload).to_bytes(4, "big") + self.payload)
        self.sent = True


def receive_vault(code: str, address: str | None = None, timeout: float = 90) -> bytes:
    """Pull a vault from a device that is offering one."""
    pairing = normalize_code(code)
    deadline = time.monotonic() + timeout
    if address and address.strip():
        host, port = _split_address(address)
        return _pull(host, port, pairing, deadline)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        udp.bind(("", UDP_PORT))
    except OSError as exc:
        udp.close()
        raise ValueError("Could not listen for the other device.") from exc
    udp.settimeout(0.5)
    try:
        while time.monotonic() < deadline:
            try:
                packet, sender = udp.recvfrom(32)
            except socket.timeout:
                continue
            if len(packet) < 6 or packet[:4] != MAGIC:
                continue
            port = int.from_bytes(packet[4:6], "big")
            return _pull(sender[0], port, pairing, deadline)
    finally:
        udp.close()
    raise ValueError("No device is offering a vault.")


def _pull(host: str, port: int, code: str, deadline: float) -> bytes:
    remaining = max(1.0, deadline - time.monotonic())
    try:
        connection = socket.create_connection((host, port), timeout=min(5.0, remaining))
    except OSError as exc:
        raise ValueError("Could not reach the other device.") from exc
    try:
        connection.settimeout(min(10.0, remaining))
        connection.sendall(MAGIC + code.encode("ascii"))
        marker = _read_exact(connection, 2)
        if marker != b"OK":
            raise ValueError("That pairing code was refused.")
        length_bytes = _read_exact(connection, 4)
        if length_bytes is None:
            raise ValueError("The other device closed the connection.")
        length = int.from_bytes(length_bytes, "big")
        if length < 48 or length > MAX_VAULT_BYTES:
            raise ValueError("The saved password file is damaged.")
        blob = _read_exact(connection, length)
        if blob is None or not blob.startswith(b"LPV"):
            raise ValueError("The saved password file is damaged.")
        return blob
    finally:
        connection.close()
