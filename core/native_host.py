import sys
import json
import struct
import subprocess
import os
import urllib.request
import urllib.error

def send_message(message: dict):
    try:
        encoded = json.dumps(message).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except Exception:
        pass

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    message_length = struct.unpack('<I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def is_falcondm_running() -> bool:
    """Checks if FalconDM local bridge server is responding."""
    try:
        req = urllib.request.Request("http://127.0.0.1:9666/ping", headers={"User-Agent": "FalconDM-NativeHost"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def launch_falcondm() -> bool:
    if is_falcondm_running():
        return True

    exe_path = sys.executable
    is_frozen_exe = getattr(sys, 'frozen', False) or exe_path.lower().endswith("falcondm.exe")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat_path = os.path.join(base_dir, "run_falcon.bat")
    main_py = os.path.join(base_dir, "main.py")
    
    try:
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creation_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            if is_frozen_exe:
                # Running from compiled FalconDM.exe
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), creationflags=creation_flags)
            elif os.path.exists(bat_path):
                subprocess.Popen([bat_path], cwd=base_dir, creationflags=creation_flags)
            else:
                subprocess.Popen([sys.executable, main_py], cwd=base_dir, creationflags=creation_flags)
        else:
            # Linux / macOS
            sh_path = os.path.join(base_dir, "run_falcon.sh")
            if is_frozen_exe:
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), start_new_session=True)
            elif os.path.exists(sh_path):
                subprocess.Popen(["bash", sh_path], cwd=base_dir, start_new_session=True)
            else:
                subprocess.Popen([sys.executable, main_py], cwd=base_dir, start_new_session=True)
        return True
    except Exception:
        return False

def forward_download_to_bridge(payload: dict) -> bool:
    """Forwards download request to FalconDM bridge HTTP server."""
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            "http://127.0.0.1:9666/download",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "FalconDM-NativeHost"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    while True:
        try:
            msg = read_message()
            if msg is None:
                break
            action = msg.get("action", "")
            if action == "ping":
                running = is_falcondm_running()
                send_message({"status": "online" if running else "offline"})
            elif action == "launch":
                ok = launch_falcondm()
                send_message({"status": "launched" if ok else "error"})
            elif action == "download":
                launch_falcondm()
                ok = forward_download_to_bridge(msg)
                send_message({"status": "queued" if ok else "launched"})
            else:
                launch_falcondm()
                send_message({"status": "ok"})
        except Exception as e:
            send_message({"status": "error", "error": str(e)})
            break

if __name__ == "__main__":
    main()
