import json
import os
import random
import socket
import string
import threading
import time
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from logging_config import setup_logging

logger = setup_logging(__name__)

try:
    import socks  # type: ignore
except Exception:  # pragma: no cover
    socks = None

try:
    import stem.process  # type: ignore
except Exception:  # pragma: no cover
    stem = None


def _rand_id(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _rand_onion() -> str:
    # Fallback pseudo-onion if tor cannot be launched.
    chars = string.ascii_lowercase + "234567"
    return "".join(random.choice(chars) for _ in range(56)) + ".onion"


def _hash_unique_id(value: str, length: int = 12) -> str:
    """
    Hash user-provided unique-id seed into a stable, non-reversible ID.
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
    return digest[:length]


@dataclass
class PlayerRecord:
    username: str
    unique_id: str
    onion: str
    port: int
    seen_at: float

    @property
    def handle(self) -> str:
        return f"{self.username}#{self.unique_id}"

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "unique_id": self.unique_id,
            "handle": self.handle,
            "onion": self.onion,
            "port": self.port,
            "seen_at": self.seen_at,
        }


class PlayerDirectoryService:
    """
    TCP overlay for player discovery with Tor hidden-service identity persistence.

    Bootstrap behavior:
    - bootstrap mode: listen on 7331 and serve peer directory
    - client mode: connect to bootstrap host:port, then gossip directly with peers
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("P2P_ENABLED", "true").lower() == "true"
        self.bootstrap_mode = os.getenv("P2P_BOOTSTRAP_MODE", "false").lower() == "true"
        self.bootstrap_host = os.getenv("P2P_BOOTSTRAP_HOST", "")
        self.bootstrap_port = int(os.getenv("P2P_BOOTSTRAP_PORT", "7331"))
        self.state_dir = Path(os.getenv("P2P_STATE_DIR", "/data/p2p")).resolve()
        self.identity_path = self.state_dir / "identity.json"
        self.hs_dir = self.state_dir / "hidden_service"
        self.hs_hostname = self.hs_dir / "hostname"
        self.hs_private_key = self.hs_dir / "hs_ed25519_secret_key"
        self.tor_data_dir = self.state_dir / "tor"
        self.enable_tor = os.getenv("P2P_ENABLE_TOR", "true").lower() == "true"
        self.socks_port = int(os.getenv("P2P_SOCKS_PORT", "9050"))

        self.username = os.getenv("PLAYER_USERNAME", os.getenv("USER", "player"))
        self.unique_id_seed = os.getenv("PLAYER_UNIQUE_ID", "").strip()
        self.unique_id = ""
        self.onion = ""
        self.listen_host = "0.0.0.0"
        self.listen_port = int(os.getenv("P2P_LISTEN_PORT", "7332"))
        if self.bootstrap_mode:
            self.listen_port = 7331

        self._tor_process = None
        self._server = None
        self._running = False
        self._lock = threading.Lock()
        self._peers: Dict[str, tuple[str, int]] = {}
        self._directory: Dict[str, PlayerRecord] = {}

    def start(self) -> None:
        if not self.enabled:
            logger.info("P2P directory disabled")
            return
        if self._running:
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._load_or_create_identity()
        self._load_or_create_hidden_service_identity()

        self._running = True
        server_thread = threading.Thread(target=self._serve, daemon=True)
        server_thread.start()

        self._upsert_local_record()

        if not self.bootstrap_mode and self.bootstrap_host:
            self._bootstrap_once(self.bootstrap_host, self.bootstrap_port)

        gossip_thread = threading.Thread(target=self._gossip_loop, daemon=True)
        gossip_thread.start()

        logger.info(
            "P2P started: handle=%s onion=%s port=%d bootstrap_mode=%s",
            self.get_local_handle(),
            self.onion,
            self.listen_port,
            self.bootstrap_mode,
        )

    def stop(self) -> None:
        self._running = False
        try:
            if self._server:
                self._server.close()
        except Exception:
            pass
        if self._tor_process is not None:
            try:
                self._tor_process.terminate()
            except Exception:
                pass
            self._tor_process = None

    def set_username(self, username: str) -> None:
        if not username:
            return
        with self._lock:
            self.username = username
            self._save_identity()
            self._upsert_local_record()

    def get_local_handle(self) -> str:
        return f"{self.username}#{self.unique_id}"

    def get_local_record(self) -> dict:
        return {
            "username": self.username,
            "unique_id": self.unique_id,
            "handle": self.get_local_handle(),
            "onion": self.onion,
            "port": self.listen_port,
        }

    def list_active_users(self) -> List[dict]:
        cutoff = time.time() - 120
        with self._lock:
            rows = [r.to_dict() for r in self._directory.values() if r.seen_at >= cutoff]
        rows.sort(key=lambda r: r["handle"].lower())
        return rows

    def resolve_handle(self, handle: str) -> Optional[dict]:
        with self._lock:
            rec = self._directory.get(handle)
            return rec.to_dict() if rec else None

    def _load_or_create_identity(self) -> None:
        # If user provides a seed, always derive the network ID from its hash.
        if self.unique_id_seed:
            self.unique_id = _hash_unique_id(self.unique_id_seed)
            self._save_identity()
            return

        if self.identity_path.exists():
            try:
                obj = json.loads(self.identity_path.read_text())
                self.username = obj.get("username", self.username)
                stored_id = obj.get("unique_id")
                if stored_id:
                    if obj.get("unique_id_hashed", False):
                        self.unique_id = str(stored_id)
                    else:
                        # Migrate legacy plain IDs to hashed form.
                        self.unique_id = _hash_unique_id(str(stored_id))
                else:
                    self.unique_id = _hash_unique_id(_rand_id())
            except Exception:
                self.unique_id = _hash_unique_id(_rand_id())
        else:
            self.unique_id = _hash_unique_id(_rand_id())
        self._save_identity()

    def _save_identity(self) -> None:
        payload = {
            "username": self.username,
            "unique_id": self.unique_id,
            "unique_id_hashed": True,
        }
        self.identity_path.write_text(json.dumps(payload))

    def _load_or_create_hidden_service_identity(self) -> None:
        self.hs_dir.mkdir(parents=True, exist_ok=True)

        if self.hs_hostname.exists() and self.hs_private_key.exists():
            self.onion = self.hs_hostname.read_text().strip()
            return

        if self.enable_tor and stem is not None:
            try:
                self.tor_data_dir.mkdir(parents=True, exist_ok=True)
                self._tor_process = stem.process.launch_tor_with_config(
                    config={
                        "SocksPort": str(self.socks_port),
                        "ControlPort": "0",
                        "DataDirectory": str(self.tor_data_dir),
                        "HiddenServiceDir": str(self.hs_dir),
                        "HiddenServicePort": f"{self.listen_port} 127.0.0.1:{self.listen_port}",
                    },
                    take_ownership=True,
                )
                # Tor should create hostname/private key in HiddenServiceDir.
                for _ in range(50):
                    if self.hs_hostname.exists():
                        break
                    time.sleep(0.1)
                if self.hs_hostname.exists():
                    self.onion = self.hs_hostname.read_text().strip()
                    return
            except Exception as exc:
                logger.warning("Tor hidden service setup failed, using fallback identity: %s", exc)

        # Fallback identity persistence if tor isn't available.
        self.onion = _rand_onion()
        self.hs_hostname.write_text(self.onion + "\n")
        self.hs_private_key.write_text("fallback-non-tor-key\n")

    def _upsert_local_record(self) -> None:
        rec = PlayerRecord(
            username=self.username,
            unique_id=self.unique_id,
            onion=self.onion,
            port=self.listen_port,
            seen_at=time.time(),
        )
        with self._lock:
            self._directory[rec.handle] = rec

    def _serve(self) -> None:
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind((self.listen_host, self.listen_port))
            self._server.listen(64)
            while self._running:
                try:
                    client, _ = self._server.accept()
                    threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
                except OSError:
                    break
        except Exception as exc:
            logger.error("P2P server failed: %s", exc)

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            try:
                data = client.recv(65535)
                if not data:
                    return
                msg = json.loads(data.decode("utf-8"))
                kind = msg.get("type")

                if kind == "bootstrap_request":
                    self._register_peer(msg.get("sender"))
                    response = {
                        "type": "bootstrap_response",
                        "peers": list(self._peers.values()),
                        "directory": [r.to_dict() for r in self.list_active_users()],
                    }
                    client.sendall(json.dumps(response).encode("utf-8"))
                elif kind == "announce":
                    self._register_peer(msg.get("sender"))
                    response = {"type": "ack", "ok": True}
                    client.sendall(json.dumps(response).encode("utf-8"))
                elif kind == "directory_request":
                    response = {
                        "type": "directory_response",
                        "directory": [r.to_dict() for r in self.list_active_users()],
                    }
                    client.sendall(json.dumps(response).encode("utf-8"))
            except Exception:
                pass

    def _register_peer(self, sender: Optional[dict]) -> None:
        if not sender:
            return
        onion = sender.get("onion")
        port = sender.get("port")
        username = sender.get("username")
        unique_id = sender.get("unique_id")
        if not onion or not port or not username or not unique_id:
            return

        handle = f"{username}#{unique_id}"
        with self._lock:
            self._peers[handle] = (onion, int(port))
            self._directory[handle] = PlayerRecord(
                username=username,
                unique_id=unique_id,
                onion=onion,
                port=int(port),
                seen_at=time.time(),
            )

    def _bootstrap_once(self, host: str, port: int) -> None:
        req = {
            "type": "bootstrap_request",
            "sender": self.get_local_record(),
        }
        rsp = self._send_request(host, port, req)
        if not rsp:
            logger.warning("Bootstrap request failed for %s:%s", host, port)
            return

        for peer in rsp.get("peers", []):
            if isinstance(peer, list) and len(peer) == 2:
                onion, p = peer[0], int(peer[1])
                if onion != self.onion or p != self.listen_port:
                    self._peers[f"{onion}:{p}"] = (onion, p)

        for rec in rsp.get("directory", []):
            self._register_peer(rec)

    def _gossip_loop(self) -> None:
        while self._running:
            self._upsert_local_record()
            peers = []
            with self._lock:
                peers = list(self._peers.values())

            announce = {"type": "announce", "sender": self.get_local_record()}
            for host, port in peers[:32]:
                if host == self.onion and int(port) == self.listen_port:
                    continue
                self._send_request(host, int(port), announce, timeout=1.5)

            if self.bootstrap_mode:
                # Bootstrap node also serves as continuously updated directory source.
                pass
            elif self.bootstrap_host:
                # Refresh view from bootstrap periodically in case peer set changed.
                self._bootstrap_once(self.bootstrap_host, self.bootstrap_port)

            time.sleep(10)

    def _open_socket(self, host: str, port: int, timeout: float) -> socket.socket:
        if host.endswith(".onion") and socks is not None:
            s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            s.set_proxy(socks.SOCKS5, "127.0.0.1", self.socks_port)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        return s

    def _send_request(self, host: str, port: int, payload: dict, timeout: float = 2.0) -> Optional[dict]:
        try:
            with self._open_socket(host, port, timeout) as s:
                s.sendall(json.dumps(payload).encode("utf-8"))
                data = s.recv(65535)
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except Exception:
            return None


_service: Optional[PlayerDirectoryService] = None


def get_service() -> PlayerDirectoryService:
    global _service
    if _service is None:
        _service = PlayerDirectoryService()
    return _service


def start_service() -> PlayerDirectoryService:
    svc = get_service()
    svc.start()
    return svc
