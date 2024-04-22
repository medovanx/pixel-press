from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import re
import os

class FFmpegProcessThread(QThread):
    progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal()

    def __init__(self, cmd, total_duration):
        super().__init__()
        self.cmd = cmd
        self.total_duration = total_duration
        self.is_cancelled = False  # Add a flag to track if the thread should be cancelled
        self.start_time = None
        self.end_time = None

    def run(self):
        print(f"Executing command: {self.cmd}")  # Debug: print the command
        process = subprocess.Popen(
            self.cmd,
            shell=True,
            stderr=subprocess.PIPE,
            text=True
        )
        time_pattern = r'time=(\d{2}):(\d{2}):(\d{2})\.(\d+)\s'

        while True:
            if self.is_cancelled:  # Check if the thread should be cancelled
                process.terminate()  # Terminate the subprocess
                break

            output_line = process.stderr.readline()
            match = re.search(time_pattern, output_line)
            if match:
                hours, minutes, seconds, mseconds = map(float, match.groups())
                total_seconds = hours * 3600 + minutes * 60 + seconds + mseconds / 1000
                progress = total_seconds / self.total_duration * 100
                self.progress_signal.emit(progress)

            if output_line == '' and process.poll() is not None:
                break

        process.wait()
        self.finished_signal.emit()

    def cancel(self):
        self.is_cancelled = True
        os.system("taskkill /f /im ffmpeg.exe")
