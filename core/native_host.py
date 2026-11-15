import sys
import json
import struct
import subprocess
import os

def send_message(message: dict):
    encoded = json.dumps(message).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    message_length = struct.unpack('<I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def launch_falcondm():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat_path = os.path.join(base_dir, "run_falcon.bat")
    main_py = os.path.join(base_dir, "main.py")
    
    try:
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            if os.path.exists(bat_path):
                subprocess.Popen([bat_path], cwd=base_dir, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen([sys.executable, main_py], cwd=base_dir, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        else:
            # Linux / macOS
            sh_path = os.path.join(base_dir, "run_falcon.sh")
            if os.path.exists(sh_path):
                subprocess.Popen(["bash", sh_path], cwd=base_dir, start_new_session=True)
            else:
                subprocess.Popen([sys.executable, main_py], cwd=base_dir, start_new_session=True)
        return True
    except Exception as e:
        return False

def main():
    while True:
        try:
            msg = read_message()
            if msg is None:
                break
            action = msg.get("action", "")
            if action in ("launch", "download"):
                ok = launch_falcondm()
                send_message({"status": "launched" if ok else "error"})
            else:
                send_message({"status": "unknown_action"})
        except Exception as e:
            send_message({"status": "error", "error": str(e)})
            break

if __name__ == "__main__":
    main()
