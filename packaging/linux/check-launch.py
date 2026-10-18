"""Confirm the installed application-menu command stays running."""
import subprocess
import time

process = subprocess.Popen(['/usr/bin/local-password'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True)
try:
    time.sleep(4)
    if process.poll() is not None:
        raise RuntimeError('Installed launcher exited: ' + process.stderr.read())
finally:
    process.terminate()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
