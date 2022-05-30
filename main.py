import sys
import json
import queue
import time
import pyqtgraph as pq
import serial
from PyQt5 import QtCore
import PyQt5.QtGui as QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from gui import Ui_MainWindow


class SerialWorker(QThread):

    data_recieved = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.com = ""
        self.baud = 0
        self.parity = ""

        self.queue = queue.Queue()
        self.running = True

        self.serial_port = serial.Serial()

    def init_serial(self):
        self.serial_port.close()
        self.serial_port.port = self.com
        self.serial_port.baudrate = self.baud
        self.serial_port.parity = self.parity
        self.serial_port.timeout = 1
        self.serial_port.stopbits = serial.STOPBITS_ONE
        self.serial_port.bytesize = serial.EIGHTBITS
        try:
            self.serial_port.open()
        except serial.SerialException:
            error_dialog = QMessageBox()
            error_dialog.setText(f"{self.com} neexistuje!")
            error_dialog.setWindowTitle("Chyba!")
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.exec_()
        else:
            success_dialog = QMessageBox()
            success_dialog.setText(f"{self.com} připojen!")
            success_dialog.setWindowTitle("Info!")
            success_dialog.setIcon(QMessageBox.Information)
            success_dialog.exec_()

    def run(self):
        while self.running:
            time.sleep(0.1)
            if not self.queue.empty():
                command = self.queue.get()
                if self.serial_port.isOpen():
                    self.serial_port.write(bytes(command, "utf-8"))
                    time.sleep(0.1)
                    data_read = self.serial_port.readline()
                    print(data_read)
                    self.data_recieved.emit(data_read.decode("utf-8"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = SerialWorker()
        self.worker.start()
        pq.setConfigOption('background', 'w')
        pq.setConfigOption('foreground', 'k')
        self.single_measurement = False
        self.periodic_measurement = False
        self.measured_data = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.measure)

        self.p_min = 1
        self.p_max = 10
        self.reference_height = 100
        self.address1 = 0

        self.gui = Ui_MainWindow()
        self.gui.setupUi(self)
        # connect buttons with function
        self.gui.push_button_send1.clicked.connect(lambda: self.send_clicked(1))
        self.gui.push_button_send2.clicked.connect(lambda: self.send_clicked(2))
        self.gui.push_button_send3.clicked.connect(lambda: self.send_clicked(3))
        self.gui.push_button_send4.clicked.connect(lambda: self.send_clicked(4))
        self.gui.push_button_send5.clicked.connect(lambda: self.send_clicked(5))

        self.gui.push_button_connect.clicked.connect(self.serial_connect)
        self.gui.push_btutton_calibration.clicked.connect(self.calibration)
        self.gui.push_button_clear_graph.clicked.connect(self.clear_graph)
        self.gui.push_button_start.clicked.connect(self.toggle_periodic)
        self.gui.push_button_measure.clicked.connect(self.one_measure)

        self.gui.radio_parity_even.toggled.connect(lambda: self.radio_clicked("even"))
        self.gui.radio_parity_odd.toggled.connect(lambda: self.radio_clicked("odd"))
        self.gui.radio_parity_no.toggled.connect(lambda: self.radio_clicked("no"))

        self.gui.radio_com_1.toggled.connect(lambda: self.radio_clicked(1))
        self.gui.radio_com_2.toggled.connect(lambda: self.radio_clicked(2))
        self.gui.radio_com_3.toggled.connect(lambda: self.radio_clicked(3))
        self.gui.radio_com_4.toggled.connect(lambda: self.radio_clicked(4))
        self.gui.radio_com_5.toggled.connect(lambda: self.radio_clicked(5))
        self.gui.radio_com_6.toggled.connect(lambda: self.radio_clicked(6))
        self.gui.radio_com_7.toggled.connect(lambda: self.radio_clicked(7))
        self.gui.radio_com_8.toggled.connect(lambda: self.radio_clicked(8))

        self.gui.radio_baud_1200.toggled.connect(lambda: self.radio_clicked(1200))
        self.gui.radio_baud_2400.toggled.connect(lambda: self.radio_clicked(2400))
        self.gui.radio_baud_4800.toggled.connect(lambda: self.radio_clicked(4800))
        self.gui.radio_baud_9600.toggled.connect(lambda: self.radio_clicked(9600))
        self.gui.radio_baud_19200.toggled.connect(lambda: self.radio_clicked(19200))

        self.worker.data_recieved.connect(self.data_processing)

        font = QtGui.QFont()
        font.setPixelSize(14)
        self.gui.widget_graph.getAxis("bottom").setStyle(tickFont=font)
        self.gui.widget_graph.getAxis("left").setStyle(tickFont=font)

        self.load_settings()

    @QtCore.pyqtSlot(str)
    def data_processing(self, input_string):
        # 2. zobrazovat jako single měření v kartě Měření
        height = 0
        if self.single_measurement or self.periodic_measurement:

            try:
                preprocess = input_string.split(",")[0]
                print("preprocessed: ", preprocess)
                data = float(preprocess.strip())
                height = self.reference_height * (data - self.p_min) / (self.p_max - self.p_min)
                self.gui.text_measured_value.setText("{:.3f}".format(height))
            except ValueError:
                error_dialog = QMessageBox()
                error_dialog.setText("Chyba při zpracování přijatých dat!")
                error_dialog.setWindowTitle("Chyba!")
                error_dialog.setIcon(QMessageBox.Critical)
                error_dialog.exec_()

            if self.single_measurement:
                self.single_measurement = False
            if self.periodic_measurement:
                self.measured_data.append(height)
                self.gui.widget_graph.plotItem.clear()
                self.gui.widget_graph.plot(self.measured_data, pen=pq.mkPen('b', width=5))
        else:
            self.gui.text_received.append(input_string)

    def toggle_periodic(self):
        if self.periodic_measurement:
            self.periodic_measurement = False
            self.gui.push_button_start.setText("Start měření")
            self.timer.stop()
        else:
            self.periodic_measurement = True
            self.gui.push_button_start.setText("Zastavit měření")
            qtime = self.gui.time_edit_period.time()
            self.timer.start((qtime.second() + qtime.minute() * 60) * 1000)

    def one_measure(self):
        self.single_measurement = True
        self.address1 = self.gui.text_edit_adr.toPlainText()
        self.worker.queue.put(f"s96;s{self.address1};msv?1;")

    def measure(self):
        self.address1 = self.gui.text_edit_adr.toPlainText()
        self.worker.queue.put(f"s96;s{self.address1};msv?1;")

    def calibration(self):
        try:
            self.p_max = float(self.gui.text_edit_max.toPlainText())
            self.p_min = float(self.gui.text_edit_min.toPlainText())
            self.reference_height = float(self.gui.text_edit_v.toPlainText())
        except ValueError:
            error_dialog = QMessageBox()
            error_dialog.setText("Zadejte pouze číslice a desetinou tečku!")
            error_dialog.setWindowTitle("Chyba!")
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.exec_()
        else:
            accepted_dialog = QMessageBox()
            accepted_dialog.setText("Zkalibrováno!")
            accepted_dialog.setWindowTitle("Info!")
            accepted_dialog.setIcon(QMessageBox.Information)
            accepted_dialog.exec_()

    def clear_graph(self):
        self.measured_data.clear()
        self.gui.widget_graph.plotItem.clear()

    def load_settings(self):
        with open("settings.json", "r") as file:
            settings = json.load(file)
        try:
            self.gui.text_send1.setText(settings["send1"])
            self.gui.text_send2.setText(settings["send2"])
            self.gui.text_send3.setText(settings["send3"])
            self.gui.text_send4.setText(settings["send4"])
            self.gui.text_send5.setText(settings["send5"])

            self.parity = settings["parity"]
            self.baud = settings["baud"]
            self.com = settings["com"]

            self.p_min = settings["min"]
            self.gui.text_edit_min.setText(str(self.p_min))

            self.p_max = settings["max"]
            self.gui.text_edit_max.setText(str(self.p_max))

            self.reference_height = settings["height"]
            self.gui.text_edit_v.setText(str(self.reference_height))

            self.address1 = settings["adr"]
            self.gui.text_edit_adr.setText(str(self.address1))

            if settings["parity"] == "no":
                self.gui.radio_parity_no.setChecked(True)
            elif settings["parity"] == "odd":
                self.gui.radio_parity_odd.setChecked(True)
            elif settings["parity"] == "even":
                self.gui.radio_parity_even.setChecked(True)

            if settings["baud"] == 2400:
                self.gui.radio_baud_2400.setChecked(True)
            elif settings["baud"] == 4800:
                self.gui.radio_baud_4800.setChecked(True)
            elif settings["baud"] == 9600:
                self.gui.radio_baud_9600.setChecked(True)
            elif settings["baud"] == 19200:
                self.gui.radio_baud_19200.setChecked(True)
            elif settings["baud"] == 1200:
                self.gui.radio_baud_1200.setChecked(True)

            if settings["com"] == 1:
                self.gui.radio_com_1.setChecked(True)
            elif settings["com"] == 2:
                self.gui.radio_com_2.setChecked(True)
            elif settings["com"] == 3:
                self.gui.radio_com_3.setChecked(True)
            elif settings["com"] == 4:
                self.gui.radio_com_4.setChecked(True)
            elif settings["com"] == 5:
                self.gui.radio_com_5.setChecked(True)
            elif settings["com"] == 6:
                self.gui.radio_com_6.setChecked(True)
            elif settings["com"] == 7:
                self.gui.radio_com_7.setChecked(True)
            elif settings["com"] == 8:
                self.gui.radio_com_8.setChecked(True)
        except KeyError:
            pass

    def radio_clicked(self, arg):
        if arg in ["no", "odd", "even"]:
            self.parity = arg
            if arg == "no":
                self.worker.parity = serial.PARITY_NONE
            elif arg == "odd":
                self.worker.parity = serial.PARITY_ODD
            else:
                self.worker.parity = serial.PARITY_EVEN

        elif arg in [1200, 2400, 4800, 9600, 19200]:
            self.baud = arg
            self.worker.baud = arg
        else:
            self.com = arg
            self.worker.com = "COM" + str(arg)

    def send_clicked(self, text_id):
        text_dict = {1: self.gui.text_send1,
                     2: self.gui.text_send2,
                     3: self.gui.text_send3,
                     4: self.gui.text_send4,
                     5: self.gui.text_send5}

        string_to_send = text_dict[text_id].toPlainText()
        self.gui.text_sent.setText(string_to_send)
        self.worker.queue.put(string_to_send)

    def closeEvent(self, event):
        # dump settings

        settings = {
            "send1": self.gui.text_send1.toPlainText(),
            "send2": self.gui.text_send2.toPlainText(),
            "send3": self.gui.text_send3.toPlainText(),
            "send4": self.gui.text_send4.toPlainText(),
            "send5": self.gui.text_send5.toPlainText(),
            "baud":  self.baud,
            "com": self.com,
            "parity": self.parity,
            "height": self.reference_height,
            "max": self.p_max,
            "min": self.p_min,
            "adr": self.address1
        }
        print("dumping, ", settings)
        with open("settings.json", "w") as file:
            json.dump(settings, file)

    def serial_connect(self):
        self.worker.init_serial()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()
