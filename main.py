from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog
from PyQt5.QtCore import QDir
from PyQt5.QtGui import *
from PyQt5.QtCore import QThread, pyqtSignal

import datetime, re
import sys, subprocess, os
import ffmpeg

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
##################### Load the User Interface file #####################
Ui_MainWindow, QtBaseClass = uic.loadUiType(resource_path(r"assets\GUI.ui"))

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
class PixelPress(QWidget, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        
        self.setupUi(self)  # load the UI file
        self.setWindowIcon(QtGui.QIcon(resource_path(r"assets\icon.png")))
        self.setFixedSize(self.size())  #make the window size fixed
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowMaximizeButtonHint)  # disable maximize button

        self.intro_btn.clicked.connect(self._selectIntroPath)
        self.input_btn.clicked.connect(self._selectInputPath)
        self.output_btn.clicked.connect(self._selectOutputPath)
        self.watermark_btn.clicked.connect(self._selectWatermarkPath)

        self.totalDuration = 0

        self.is_compression_cancelled = False
        self.process_thread = None
        self.process_btn.clicked.connect(self.toggleCompression)
        self._checkFFmpeg()
        self.initial_directory = str(QDir.homePath()) + "/Desktop"

    def _checkFFmpeg(self):
        # Run the ffmpeg -version command and capture its output
        try:
            result = subprocess.check_output(['ffmpeg', '-version'], stderr=subprocess.STDOUT, text=True)
            version_lines = [line for line in result.split('\n') if line.startswith('ffmpeg version')]
            if version_lines:
                ffmpeg_version = version_lines[0].split(' ')[2]
                self.ffmpeg_version.setText('FFmpeg version: ' + ffmpeg_version)
                self.status_label.setText('The program is ready!')
                self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12px")
            else:
                self.status_label.setText('Error: FFmpeg not found.<br>Please download FFmpeg from <a href="https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z">here</a>')
                self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px")
        except subprocess.CalledProcessError:
            self.status_label.setText('Unknown error.')

    def _getDuration(self, path) -> float:
        """Get the duration of the video"""
        probe = ffmpeg.probe(path, show_entries="format=duration", select_streams="a:0")
        return float(probe["format"]["duration"])
    
    def _selectIntroPath(self):
        """Get the path of the intro file selected by the user"""
        filename, _ = QFileDialog.getOpenFileName(self, 'Select intro file', directory=self.initial_directory, filter='Video files (*.mp4 *.avi *.mkv *.wmv *.m4v)')
        
        if filename:
            self.intro_file.setText(filename)           # set the text field the intro line to the selected file path
            self.intro_path = self.intro_file.text()    # get the intro file path

            self.totalDuration += self._getDuration(self.intro_path)

    def _selectInputPath(self):
        """Get the path of the input file selected by the user"""
        filename, _ = QFileDialog.getOpenFileName(self, 'Select input file', directory=self.initial_directory, filter='Video files (*.mp4 *.avi *.mkv *.wmv *.m4v)')
        if filename:
            self.input_file.setText(filename) 
            self.input_path = self.input_file.text()
            
            # Output path
            self.output_path = self.input_path.rsplit(".", 1)[0] + '_COMPRESSED.mp4'   
            self.output_file.setText(self.output_path.replace("\\", "/"))

            self.totalDuration += self._getDuration(self.input_path)

    def _selectOutputPath(self):
        """Get the path of the output file selected by the user"""
        filename, _ = QFileDialog.getSaveFileName(self, 'Select output destination', directory=self.initial_directory, filter='Video files (*.mp4)')
        self.output_file.setText(filename)
        self.output_path = self.output_file.text()

    def _selectWatermarkPath(self):
        """Get the path of the watermark file selected by the user"""
        filename, _ = QFileDialog.getOpenFileName(self, 'Select watermark file', directory=self.initial_directory, filter='Image files (*.png *.jpg *.jpeg)')
        self.watermark_file.setText(filename)
        self.watermark_path = self.watermark_file.text()

    @staticmethod
    def _cleanPath(path) -> str:
        """Clean the path of the file from quotes"""
        return path.strip('\"')
    
    def _getOriginalVideo(self, input_path, scale='1280x720') -> tuple:
        """Get the original video and audio streams"""
        input_stream = ffmpeg.input(f'"{input_path}"')
        return input_stream.video.filter('scale', size=scale), input_stream.audio
    
    def _addWatermark(self, video_stream, watermark_path, logo_size, position) -> ffmpeg.nodes.FilterableStream:
        """Add a watermark to the video"""
        watermark = ffmpeg.input(f'"{watermark_path}"')
        x = 10 if 'left' in position else 'main_w-overlay_w-10'
        y = 10 if 'top' in position else 'main_h-overlay_h-10'
        overlay_stream = video_stream.overlay(watermark.filter('scale', size=logo_size), x=x, y=y)
        return overlay_stream
    
    def _SwitchButtonToCompression(self):
        '''Switch the button to "Compress"'''
        self.process_btn.setText("Compress")
        self.process_btn.setStyleSheet("QPushButton {color: #FFFFFF; font-family: Verdana; font-size: 15px; font-weight: bold; padding: 6px; background-color: #1BC466; border-radius: 10px;} QPushButton:hover {background:#159e51;}")

    def _SwitchButtonToCancel(self):
        '''Switch the button to "Cancel"'''
        self.process_btn.setText("Cancel")
        self.process_btn.setStyleSheet("QPushButton {color: #FFFFFF; font-family:system-ui; font-size: 15px; font-weight: bold; padding: 6px; background-color: #FF0000; border-radius: 10px;} QPushButton:hover {background:#c70000;}")
            
    def toggleCompression(self):
        """Start or cancel the video compression"""
        if self.process_thread and self.process_thread.isRunning():
            # If the process thread is running, cancel it
            self.is_compression_cancelled = True
            self.process_thread.cancel()
            self._SwitchButtonToCompression()
        else:
            # If the process thread is not running, start the compression
            self.is_compression_cancelled = False
            self._SwitchButtonToCancel()
            
            # Record the start time
            self.start_time = datetime.datetime.now()

            try:
                self.intro_path = self._cleanPath(self.intro_file.text())
                self.input_path = self._cleanPath(self.input_file.text())
                self.output_path = self._cleanPath(self.output_file.text())
                self.watermark_path = self._cleanPath(self.watermark_file.text())
                video_stream, audio_stream = self._getOriginalVideo(self.input_path)

                # Check if input and output files are selected
                if (self.input_path == '' or self.output_path == ''):
                    self.status_label.setText('Error: Please select an input and output file!')
                    self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px")
                    return
                
                # Check if an intro file is selected
                if self.intro_path:
                    intro_stream, intro_audio_stream = self._getOriginalVideo(self.intro_path)
                    video_stream = ffmpeg.concat(intro_stream, video_stream, v=1, a=0)
                    audio_stream = ffmpeg.concat(intro_audio_stream, audio_stream, v=0, a=1)

                # Check if a watermark file is selected
                if self.watermark_path:
                    logo_size = self.watermark_size.text() or '125x125'
                    position = self.watermark_position.currentText().lower()
                    video_stream = self._addWatermark(video_stream, self.watermark_path, logo_size, position)

                # Compress the video to H.264 codec with CRF=28 and scale to 720p resolution
                output_stream = ffmpeg.output(video_stream, audio_stream, f'"{self.output_path}"', crf=28, vcodec='libx264', vsync=2)

                # Check if input and output files are selected
                if (self.input_path == '' or self.output_path == ''):
                    raise Exception('Please select an input and output file!')
                elif not os.path.exists(self.input_path):
                    raise Exception('Input file does not exist!')
                elif not self.output_path.endswith('.mp4'):
                    raise Exception('Output file must be an mp4 file!')
                
                if self.debug_btn.isChecked():
                    self.runInDebugMode(output_stream)
                else:
                    self.runInNormalMode(output_stream)

            except Exception as e:
                print(e)
                self.status_label.setText('Error: ' + str(e))
                self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px")

    def runInDebugMode(self, output_stream):
        """Run the ffmpeg command in debug mode, still not implemented"""
        cmd = ' '.join(ffmpeg.compile(output_stream, overwrite_output=True))
        self.process_thread = FFmpegProcessThread(cmd, self.totalDuration)
        self.process_thread.progress_signal.connect(self.updateProgress)
        self.process_thread.finished_signal.connect(self.processingFinished)
        self.process_thread.start()

        self.status_label.setText('Running in debug mode!')
        self.status_label.setStyleSheet("color: #900c3f; font-weight: bold; font-size: 14px")

    def runInNormalMode(self, output_stream):
        """Run the ffmpeg command in normal mode"""
        cmd = ' '.join(ffmpeg.compile(output_stream, overwrite_output=True))
        self.process_thread = FFmpegProcessThread(cmd, self.totalDuration)
        self.process_thread.progress_signal.connect(self.updateProgress)
        self.process_thread.finished_signal.connect(self.processingFinished)
        self.process_thread.start()

        self.status_label.setText('Running in normal mode!')
        self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px")

    def updateProgress(self, progress):
        """Update the progress bar of the video compression"""
        elapsed_time = (datetime.datetime.now() - self.start_time).total_seconds()
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        elapsed_time_text = f'<span style="font-size: 11px; color:black;">Elapsed time: {elapsed_minutes} minutes and {elapsed_seconds} seconds</span>'

        self.status_label.setText(f'Progress {progress:.2f}%<br>{elapsed_time_text}')
        QApplication.processEvents()

    def processingFinished(self):
        self.end_time = datetime.datetime.now()
        elapsed_time = (self.end_time - self.start_time).total_seconds()
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        elapsed_time_text = f'<span style="font-size: 11px; color:black;">Elapsed time: {elapsed_minutes} minutes and {elapsed_seconds} seconds</span>'

        if self.is_compression_cancelled:
            self.status_label.setText(f'Video processing cancelled!<br>{elapsed_time_text}')
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px")
        else:
            self.status_label.setText(f'Video processing complete!<br>{elapsed_time_text}')
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px")

        # Reset the button to "Compress" after the process finishes
        self._SwitchButtonToCompression()
        
        if self.process_thread:
            self.process_thread.wait()    # Wait for the thread to finish

        self.process_thread = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    video_processor = PixelPress()
    video_processor.show()

    sys.exit(app.exec_())