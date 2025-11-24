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

def binarize(im, thresh=128):
    im = im.convert('L')
    a = np.array(im)
    return (a < thresh).astype(np.uint8)

def patterns():
    return [[1,0], [0,1]]

def generate_multiple_shares(input_path, out_prefix, n):
    if not os.path.exists(input_path):
        print(f"Input not found: {input_path}")
        return
    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"Failed to open input: {e}")
        return

    bw = binarize(img)
    if bw.size == 0:
        print("Binarized image is empty")
        return

    h, w = bw.shape
    print(f"Input size (h,w): {h},{w}, generating {n} shares")

    out_h = h * 2
    out_w = w * 2
    shares = [np.full((out_h, out_w), 255, dtype=np.uint8) for _ in range(n)]
    pats = patterns()

    for y in range(h):
        for x in range(w):
            p = random.choice(pats)
            # for white pixels all shares use same pattern p
            if bw[y, x] == 0:
                assignments = [p] * n
            else:
                # start with random assignments (p or ~p)
                assignments = [random.choice([p, [1-b for b in p]]) for _ in range(n)]
                # ensure at least one p and one ~p so stacking can produce dark block
                if not any(a == p for a in assignments):
                    assignments[random.randrange(n)] = p
                if not any(a != p for a in assignments):
                    idx = random.randrange(n)
                    assignments[idx] = [1-b for b in p]

            # write into 2x2 block per share
            for share_idx, s_pat in enumerate(assignments):
                for dy in (0,1):
                    yy = y * 2 + dy
                    shares[share_idx][yy, x*2    ] = 0 if s_pat[0] else 255
                    shares[share_idx][yy, x*2 + 1] = 0 if s_pat[1] else 255

    filenames = []
    for i, arr in enumerate(shares, start=1):
        fname = f"{out_prefix}_{i}.png"
        d = os.path.dirname(fname)
        if d and not os.path.exists(d):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                print(f"Failed to create directory {d}: {e}")
                return
        try:
            Image.fromarray(arr).save(fname, format='PNG')
            filenames.append(fname)
        except Exception as e:
            print(f"Failed to save {fname}: {e}")
            return

    print("Saved shares:", ", ".join(os.path.abspath(f) for f in filenames))
    return filenames

def reconstruct(share_paths, out_path):
    # accept either a single string or a list of share paths
    if isinstance(share_paths, str):
        share_paths = [share_paths]
    for p in share_paths:
        if not os.path.exists(p):
            print(f"Share not found: {p}")
            return
    try:
        arrs = [np.array(Image.open(p).convert('L')) for p in share_paths]
    except Exception as e:
        print(f"Failed to open shares: {e}")
        return
    # ensure all same shape
    shapes = {a.shape for a in arrs}
    if len(shapes) != 1:
        print("Share sizes differ")
        return
    # stacking: min over all shares
    recon = arrs[0].copy()
    for a in arrs[1:]:
        recon = np.minimum(recon, a)
    d = os.path.dirname(out_path)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            print(f"Failed to create directory {d}: {e}")
            return
    try:
        Image.fromarray(recon).save(out_path, format='PNG')
    except Exception as e:
        print(f"Failed to save reconstruction: {e}")
        return
    print(f"Saved reconstruction: {os.path.abspath(out_path)}")

def send_file_to_target(file_path, host, port, timeout=5):
    try:
        size = os.path.getsize(file_path)
    except Exception as e:
        print(f"Failed to stat {file_path}: {e}")
        return False
    fname = os.path.basename(file_path).encode("utf-8")
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            # send filename length + filename
            s.sendall(struct.pack("!I", len(fname)))
            s.sendall(fname)
            # send 8-byte file size
            s.sendall(struct.pack("!Q", size))
            # stream file contents in chunks
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    s.sendall(chunk)
        print(f"SENT: {file_path} -> {host}:{port}")
        return True
    except Exception as e:
        print(f"Send failed {file_path} -> {host}:{port}: {e}")
        return False

def send_shares_over_network(share_paths, targets, default_port=8000, timeout=5):
    if isinstance(share_paths, str):
        share_paths = [share_paths]
    # normalize targets (accept "host", "host:port", or list/tuple entries)
    if isinstance(targets, str):
        # accept separators ; or ,
        targets = [t for t in re.split(r"[;,]", targets) if t]
    norm = []
    for t in targets:
        if isinstance(t, str):
            t = t.strip()
            if not t:
                continue
            if ":" in t:
                h, p = t.rsplit(":", 1)
                try:
                    norm.append((h, int(p)))
                except Exception:
                    # fallback to None so we assign ports later
                    norm.append((h, None))
            else:
                # host only -> mark port as None so we'll auto-assign per-share
                norm.append((t, None))
        elif isinstance(t, (list, tuple)) and len(t) >= 2:
            try:
                norm.append((t[0], int(t[1])))
            except Exception:
                norm.append((t[0], None))
    if not norm:
        print("No valid targets provided")
        return [False] * len(share_paths)

    results = []
    # assign ports automatically for entries with None: use default_port + global share index
    base_port = int(default_port)
    for i, sp in enumerate(share_paths):
        host, port = norm[i % len(norm)]
        if port is None:
            assigned_port = base_port + i
        else:
            assigned_port = port
        ok = send_file_to_target(sp, host, assigned_port, timeout=timeout)
        results.append(ok)
    return results

def recv_exact(conn, n):
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("socket closed")
            buf.extend(chunk)
        except socket.timeout:
            # timeout just gives us a chance to check for interrupts/stop flags
            continue
    return bytes(buf)

def start_receiver(listen_host, listen_port, dest_dir, max_files=None, reconstruct_after=None, reconstruct_out="reconstruction.png", shared_state=None):
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
        print(f"Receiver listening on {listen_host}:{listen_port}, saving to {dest_dir}")
        while True:
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
                continue
            try:
                # make client socket non-blocking by using timeouts so KeyboardInterrupt/stop can be detected
                conn.settimeout(1.0)

                # read filename length
                raw = recv_exact(conn, 4)
                name_len = struct.unpack("!I", raw)[0]
                name = recv_exact(conn, name_len).decode("utf-8", errors="ignore")
                size = struct.unpack("!Q", recv_exact(conn, 8))[0]
                # read file data
                data = bytearray()
                remaining = size
                while remaining:
                    try:
                        chunk = conn.recv(min(65536, remaining))
                        if not chunk:
                            raise ConnectionError("socket closed while receiving file")
                        data.extend(chunk)
                        remaining -= len(chunk)
                    except socket.timeout:
                        # allow periodic checks for KeyboardInterrupt / shared stop
                        continue
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
                    print(f"RECEIVED from {addr}: {out_path} ({size} bytes)")

            except Exception as e:
                print(f"Failed receiving from {addr}: {e}")
            finally:
                conn.close()

            # optionally reconstruct (use shared_state for cross-listener totals)
            try:
                if shared_state:
                    recon_after = shared_state.get("reconstruct_after")
                    # perform reconstruction only once
                    do_recon = False
                    with shared_state["lock"]:
                        if recon_after and not shared_state.get("reconstructed") and shared_state.get("count", 0) >= int(recon_after):
                            shared_state["reconstructed"] = True
                            do_recon = True
                    if do_recon:
                        files = sorted([os.path.join(dest_dir, f) for f in os.listdir(dest_dir)])
                        reconstruct(files, os.path.join(dest_dir, shared_state.get("reconstruct_out", reconstruct_out)))
                else:
                    if reconstruct_after and current_total >= int(reconstruct_after):
                        files = sorted([os.path.join(dest_dir, f) for f in os.listdir(dest_dir)])
                        reconstruct(files, os.path.join(dest_dir, reconstruct_out))
            except Exception as e:
                print(f"Auto-reconstruct failed: {e}")

            # exit conditions
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
        server.close()

def __main_cli_send_patch():
    pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python viscrypt.py gen input.png out_prefix n [--send hosts] [--send-port start_port]")
        print("    --send hosts: semicolon/comma separated hosts (host or host:port).")
        print("    If a host has no :port it will be auto-assigned per-share starting from start_port (default 8000).")
        print("  python viscrypt.py recv host port dest_dir [--max n] [--reconstruct-after k]")
        sys.exit(1)
    cmd = sys.argv[1].lower()

    if cmd == "gen" and len(sys.argv) >= 5:
        _,_, inp, out_prefix, n = sys.argv[:5]
        extra = sys.argv[5:]
        files = None
        if n.isdigit():
            files = generate_multiple_shares(inp, out_prefix, int(n))
        else:
            # legacy two-output mode: out_prefix and n treated as two filenames
            temp_prefix = os.path.splitext(out_prefix)[0] + "_vc_temp"
            files = generate_multiple_shares(inp, temp_prefix, 2)
            if files and len(files) == 2:
                try:
                    shutil.move(files[0], out_prefix)
                    shutil.move(files[1], n)
                    files = [out_prefix, n]
                    print(f"Saved shares: {os.path.abspath(out_prefix)}, {os.path.abspath(n)}")
                except Exception as e:
                    print(f"Failed to rename temporary shares: {e}")
                    files = None

        # optional: send shares over network
        if files and "--send" in extra:
            try:
                i = extra.index("--send")
                if i+1 >= len(extra):
                    print("Missing targets after --send")
                else:
                    raw = extra[i+1]
                    # hosts like host1;host2 or host1:port1;host2:port2
                    # optional --send-port to set starting port for hosts without explicit port
                    send_port = 8000
                    if "--send-port" in extra:
                        try:
                            j = extra.index("--send-port")
                            if j+1 < len(extra):
                                send_port = int(extra[j+1])
                        except Exception:
                            pass
                    results = send_shares_over_network(files, raw, default_port=send_port)
                    print("Send results:", results)
            except Exception as e:
                print(f"Send failed: {e}")

    elif cmd in ("recv", "serve") and len(sys.argv) >= 5:
        _, _, host, port, dest_dir, *extra = sys.argv
        max_n = None
        recon_after = None
        if "--max" in extra:
            try:
                i = extra.index("--max"); max_n = int(extra[i+1])
            except Exception:
                pass
        if "--reconstruct-after" in extra:
            try:
                i = extra.index("--reconstruct-after"); recon_after = int(extra[i+1])
            except Exception:
                pass

        # Support multiple ports (e.g. "8000;8001" or "8000,8001")
        port_seps = [p for p in re.split(r"[;,]", port) if p]
        if len(port_seps) <= 1:
            # single listener (existing behavior)
            start_receiver(host, port, dest_dir, max_files=max_n, reconstruct_after=recon_after)
        else:
            # spawn one listener thread per port, use shared_state so totals/reconstruct are global
            shared_state = {
                "lock": threading.Lock(),
                "count": 0,
                "max_files": max_n,
                "reconstruct_after": recon_after,
                "reconstructed": False,
                "reconstruct_out": "reconstruction.png"
            }
            threads = []
            for p in port_seps:
                t = threading.Thread(
                    target=start_receiver,
                    args=(host, p, dest_dir),
                    kwargs={"shared_state": shared_state},
                    daemon=False
                )
                t.start()
                threads.append(t)
                print(f"Started receiver thread for {host}:{p}, saving to {dest_dir}")
            # Wait for threads to finish (they will exit when global max_files reached if provided)
            for t in threads:
                t.join()