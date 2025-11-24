from PIL import Image
import numpy as np
import random
import sys
import os
import shutil
import time
import socket
import struct
import threading
import re
import signal

def recv_exact(conn, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf.extend(chunk)
    return bytes(buf)

def start_receiver(listen_host, listen_port, dest_dir, max_files=None, shared_state=None, stop_file=None, stop_event=None):
    if not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create dest dir {dest_dir}: {e}")
            return
    listen_addr = (listen_host, int(listen_port))
    received = 0
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(listen_addr)
        server.listen(5)
        # set short timeout so accept() wakes periodically to check stop_event / stop_file
        server.settimeout(1.0)
        print(f"Receiver listening on {listen_host}:{listen_port}, saving to {dest_dir}")
        while True:
            # check stop_event or stop_file before blocking on accept
            if stop_event and stop_event.is_set():
                print("Stop event set, exiting listener.")
                break
            if stop_file and os.path.exists(stop_file):
                print(f"Stop file detected ({stop_file}), exiting listener.")
                break

            # if using shared_state and global max_files reached, exit
            if shared_state:
                with shared_state["lock"]:
                    gcount = shared_state.get("count", 0)
                if shared_state.get("max_files") and gcount >= int(shared_state["max_files"]):
                    print(f"Global max_files reached ({gcount}), listener {listen_port} exiting.")
                    break

            try:
                conn, addr = server.accept()
            except socket.timeout:
                # timed out; loop to re-check stop conditions
                continue
            except KeyboardInterrupt:
                print("KeyboardInterrupt, shutting down listener.")
                break
            except Exception as e:
                print(f"Accept failed: {e}")
                break

            try:
                # read filename length
                raw = recv_exact(conn, 4)
                name_len = struct.unpack("!I", raw)[0]
                name = recv_exact(conn, name_len).decode("utf-8", errors="ignore")
                size = struct.unpack("!Q", recv_exact(conn, 8))[0]
                # read file data
                data = bytearray()
                remaining = size
                while remaining:
                    chunk = conn.recv(min(65536, remaining))
                    if not chunk:
                        raise ConnectionError("socket closed while receiving file")
                    data.extend(chunk)
                    remaining -= len(chunk)
                # save file (avoid overwriting)
                out_path = os.path.join(dest_dir, name)
                if os.path.exists(out_path):
                    base, ext = os.path.splitext(name)
                    idx = 1
                    while True:
                        candidate = os.path.join(dest_dir, f"{base}_{idx}{ext}")
                        if not os.path.exists(candidate):
                            out_path = candidate
                            break
                        idx += 1
                with open(out_path, "wb") as f:
                    f.write(data)

                # update counters (shared or local)
                if shared_state:
                    with shared_state["lock"]:
                        shared_state["count"] = shared_state.get("count", 0) + 1
                        current_total = shared_state["count"]
                    print(f"RECEIVED from {addr}: {out_path} ({size} bytes) -- global count {current_total}")
                else:
                    received += 1
                    current_total = received
                    print(f"RECEIVED from {addr}: {out_path} ({size} bytes) -- total {current_total}")

            except Exception as e:
                print(f"Failed receiving from {addr}: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            # exit conditions
            if stop_event and stop_event.is_set():
                print("Stop event set, exiting listener.")
                break
            if stop_file and os.path.exists(stop_file):
                print(f"Stop file detected ({stop_file}), exiting listener.")
                break

            if shared_state:
                with shared_state["lock"]:
                    if shared_state.get("max_files") and shared_state.get("count", 0) >= int(shared_state["max_files"]):
                        print("Global required number of files received, exiting receiver.")
                        break
            else:
                if max_files and received >= int(max_files):
                    print("Received required number of files, exiting receiver.")
                    break
    except Exception as e:
        print(f"Receiver error: {e}")
    finally:
        try:
            server.close()
        except Exception:
            pass

# Add a simple control listener to set the stop event remotely
def start_control_listener(listen_host, control_port, stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((listen_host, int(control_port)))
        sock.listen(1)
        print(f"Control listener on {listen_host}:{control_port} (send any connection or 'STOP' to stop)")
        conn, addr = sock.accept()
        try:
            # read small amount; presence of connection is enough
            try:
                data = conn.recv(64)
                if data and data.strip().upper() == b"STOP":
                    print("Received STOP command on control port.")
            except Exception:
                pass
            stop_event.set()
        finally:
            conn.close()
    except Exception as e:
        print(f"Control listener error: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python attacker.py recv host port dest_dir")
        sys.exit(1)
    cmd = sys.argv[1].lower()

    if cmd in ("recv", "serve") and len(sys.argv) >= 5:
        _, _, host, port, dest_dir, *extra = sys.argv
        max_n = None
        stop_file = None
        stop_port = None
        if "--max" in extra:
            try:
                i = extra.index("--max"); max_n = int(extra[i+1])
            except Exception:
                pass
        if "--stop-file" in extra:
            try:
                i = extra.index("--stop-file"); stop_file = extra[i+1]
            except Exception:
                pass
        if "--stop-port" in extra:
            try:
                i = extra.index("--stop-port"); stop_port = int(extra[i+1])
            except Exception:
                pass

        # Support multiple ports (e.g. "8000;8001" or "8000,8001")
        port_seps = [p for p in re.split(r"[;,]", port) if p]
        if len(port_seps) <= 1:
            stop_event = threading.Event()
            # handle Ctrl+C in main thread by setting stop_event
            def _on_sigint(signum, frame):
                print("SIGINT received, stopping listener...")
                stop_event.set()
            signal.signal(signal.SIGINT, _on_sigint)
            # optionally start control listener
            if stop_port:
                threading.Thread(target=start_control_listener, args=(host, stop_port, stop_event), daemon=True).start()
            start_receiver(host, port, dest_dir, max_files=max_n, shared_state=None, stop_file=stop_file, stop_event=stop_event)
        else:
            shared_state = {
                "lock": threading.Lock(),
                "count": 0,
                "max_files": max_n,
                "stop_event": threading.Event()
            }
            # install SIGINT handler to set shared stop_event for all threads
            def _on_sigint_shared(signum, frame):
                print("SIGINT received, stopping all listeners...")
                shared_state["stop_event"].set()
            signal.signal(signal.SIGINT, _on_sigint_shared)
            threads = []
            # start control listener once if requested (shares same stop_event)
            if stop_port:
                threading.Thread(target=start_control_listener, args=(host, stop_port, shared_state["stop_event"]), daemon=True).start()
            for p in port_seps:
                t = threading.Thread(
                    target=start_receiver,
                    args=(host, p, dest_dir),
                    kwargs={"shared_state": shared_state, "stop_file": stop_file, "stop_event": shared_state["stop_event"]},
                    daemon=False
                )
                t.start()
                threads.append(t)
                print(f"Started receiver thread for {host}:{p}, saving to {dest_dir}")
            # Wait for threads to finish (they will exit when global max_files reached or stop_event triggered)
            for t in threads:
                t.join()