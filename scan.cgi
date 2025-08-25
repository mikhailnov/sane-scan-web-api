#!/usr/bin/env python3
import subprocess
import base64
import sys
import tempfile
import os
import threading
import time

def read_stderr(stderr, progress_event):
    buffer = ""
    while True:
        chunk = stderr.read(1).decode(errors='ignore')
        if not chunk:  # Конец потока
            break
        if chunk == '%':
            print(f"DEBUG: {buffer}", file=sys.stderr)
            if "100.0" in buffer:
                print("DONE! Progress 100% reached", file=sys.stderr)
                progress_event.set()
            buffer = ""
        else:
            buffer += chunk
    stderr.close()
    print("DEBUG: stderr reader thread exited", file=sys.stderr)

try:
    # Создаём временный файл
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        temp_path = tmp_file.name

    # Запускаем процесс сканирования
    process = subprocess.Popen(
        [
            'scanimage',
            '--format=jpeg',
            '--resolution=300',
            '--mode=Color',
            '--device-name=genesys:libusb:001:040',
            '--progress',
            f'--output-file={temp_path}'
        ],
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL
    )

    progress_event = threading.Event()
    stderr_thread = threading.Thread(
        target=read_stderr,
        args=(process.stderr, progress_event)
    )
    stderr_thread.daemon = True  # Поток завершится с основным процессом
    stderr_thread.start()

    # Основной цикл ожидания
    while process.poll() is None:  # Пока процесс работает
        if progress_event.wait(0.2):  # Проверяем прогресс каждые 200 мс
            print("DEBUG: Detected 100% progress", file=sys.stderr)
            break

    time.sleep(1)

    # Чтение и кодирование изображения
    with open(temp_path, 'rb') as f:
        img_data = f.read()

    if not img_data:
        raise RuntimeError("No image data received")

    img_base64 = base64.b64encode(img_data).decode('utf-8')

    # Вывод результата
    print("Content-Type: application/json")
    print("Access-Control-Allow-Origin: *\n")
    print(f'{{"image": "{img_base64}"}}')

except Exception as e:
    print("Content-Type: application/json")
    print("Access-Control-Allow-Origin: *\n")
    error_msg = f"Scan error: {str(e)}"
    if isinstance(e, subprocess.CalledProcessError):
        error_msg += f" (exit code {e.returncode})"
    print(f'{{"error": "{error_msg}"}}')
    sys.exit(1)

finally:
    # Удаление временного файла
    if 'temp_path' in locals() and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception as e:
            print(f"WARNING: Failed to delete temp file: {str(e)}", file=sys.stderr)
