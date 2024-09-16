import sys
import socket
import time
import math
import threading
from PyQt5 import QtWidgets
from pyqtgraph import PlotWidget, plot  # type: ignore
import pyqtgraph as pg  # type: ignore

# UDP ayarları
UDP_IP = "127.0.0.1"
SEND_PORT = 8081  # Python'dan QT'ye veri gönderme portu
RECEIVE_PORT = 8080  # Python'un QT'den veri aldığı port
BUFFER_SIZE = 1024

# Global değişkenler
udp_period = None  # Varsayılan değer yok
sinus_period = None  # Varsayılan değer yok
stop_event = threading.Event()  # Durdurma olayı için Event
resume_event = threading.Event()  # Tekrar başlatma olayı
resume_event.set()  # Başlangıçta devam etmeye ayarlı

# Açı değerlerini saklayacak listeler
received_angles_8080 = []  # 8080 portundan alınan açı değerleri
sent_angles_8081 = []  # 8081 portuna gönderilen açı değerleri

# PyQt5 arayüzü
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # Arayüz ayarları
        self.setWindowTitle("Roket kanatçık Simülasyonu")

        # İki adet grafik penceresi oluştur
        self.graphWidget1 = pg.PlotWidget()
        self.graphWidget2 = pg.PlotWidget()

        # İlk grafiği yerleştir (8080'den alınan açılar)
        self.graphWidget1.setTitle("8080 Portundan Alınan Açılar")
        self.graphWidget1.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget1.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget1.setYRange(-180, 180)

        # İkinci grafiği yerleştir (8081'e gönderilen sinüs değerleri)
        self.graphWidget2.setTitle("8081 Portuna Gönderilen Sinüs Sinyalleri")
        self.graphWidget2.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget2.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget2.setYRange(-180, 180)

        # Ana widget ayarları
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.graphWidget1)
        layout.addWidget(self.graphWidget2)

        # Merkezi widget ayarla
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Gerçek zamanlı veri güncelleme için zamanlayıcı
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)  # 100 ms'de bir grafik güncellemesi

    def update_plots(self):
        # 8080'den alınan açı değerlerini çizdir
        self.graphWidget1.plot(received_angles_8080, pen=pg.mkPen(color='b'), clear=True)

        # 8081'e gönderilen sinüs değerlerini çizdir
        self.graphWidget2.plot(sent_angles_8081, pen=pg.mkPen(color='r'), clear=True)

# Sinüs sinyali gönderimi için fonksiyon
def send_sinusoidal_signal(ip, port):
    global sinus_period, udp_period, stop_event, resume_event, sent_angles_8081
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.time()

    while not stop_event.is_set():
        if sinus_period is not None and udp_period is not None and resume_event.is_set():
            elapsed_time = time.time() - start_time
            t = elapsed_time * 1000  # Milisaniye cinsine çevriliyor
            if sinus_period != 0:
                # Sinüs sinyalini derece cinsinden hesapla
                angle = (360 * t / sinus_period) % 360
                # Sinüs sinyalini -180 ile +180 arasında hesapla
                sinus_value = int(round(math.sin(math.radians(angle)) * 180))
                # -180 ile +180 arasında sınırlama yap
                sinus_value = max(-180, min(180, sinus_value))
            else:
                sinus_value = 0  # Eğer periyot sıfırsa sinüs sinyali 0 olur

            message = str(sinus_value).encode()  # Açı cinsinden integer olarak gönder
            sock.sendto(message, (ip, port))
            print(f"Sent sinusoidal value: {sinus_value}")

            # Gönderilen açı değerini kaydet
            sent_angles_8081.append(sinus_value)
            if len(sent_angles_8081) > 100:  # Sadece son 100 değeri sakla
                sent_angles_8081.pop(0)

            time.sleep(udp_period / 1000.0)  # UDP periyoduna göre sinyal gönderiliyor
        else:
            print("Waiting for UDP period and sinus period settings or communication stopped.")
            # Eğer sinüs sinyali gönderilmiyorsa, listeye sıfır ekle
            sent_angles_8081.append(0)
            if len(sent_angles_8081) > 100:  # Sadece son 100 değeri sakla
                sent_angles_8081.pop(0)
            time.sleep(1)  # Ayarların gelmesini beklemek için bekleme süresi

    sock.close()  # Socket'i kapat

# Veri alma ve parametreleri ayarlama fonksiyonu
def receive_data(ip, port):
    global udp_period, sinus_period, stop_event, resume_event, received_angles_8080
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))

    last_received_time = time.time()  # Son veri alınma zamanı
    
    while not stop_event.is_set():
        sock.settimeout(1.0)  # 1 saniyelik zaman aşımı
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode().strip()  # Gelen veri decode edilip boşluklar temizleniyor
            print(f"Received data: {decoded_data}")

            last_received_time = time.time()  # Veri alındığında zamanı güncelle

            try:
                angle_value = int(decoded_data)
                # Gelen açı değerini kaydet
                received_angles_8080.append(angle_value)
                if len(received_angles_8080) > 100:  # Sadece son 100 değeri sakla
                    received_angles_8080.pop(0)

            except ValueError:
                # Veri iki parçaya ayrılıyor
                data_parts = decoded_data.split(',')
                if len(data_parts) == 2:
                    try:
                        udp_period = int(data_parts[0])  # İlk veri: UDP veri gönderme periyodu (milisaniye)
                        sinus_period = int(data_parts[1])  # İkinci veri: Sinüs sinyalinin periyodu (milisaniye)
                        print(f"UDP period set to: {udp_period}, Sinus period set to: {sinus_period}")
                        resume_event.set()  # Yeni veri geldiğinde sinyali tekrar başlat
                    except ValueError:
                        print(f"Invalid data received: {decoded_data}")  # Hatalı veri varsa göster
                        stop_event.set()  # Hata durumunda durdurma olayını işaretle
                else:
                    if decoded_data == "UDP communication stopped.":
                        print("UDP communication stopped.")
                        resume_event.clear()  # Sinyal gönderimini durdur
                    else:
                        print("Data format is incorrect. Expected two values separated by a comma.")
        except socket.timeout:
            # Zaman aşımı durumunda, veri gelmediğinde 0 ekle
            elapsed_since_last_received = time.time() - last_received_time
            if elapsed_since_last_received >= 1.0:  # 1 saniyede veri gelmediyse 0 ekle
                received_angles_8080.append(0)
                if len(received_angles_8080) > 100:  # Sadece son 100 değeri sakla
                    received_angles_8080.pop(0)
                print("No data received, appending 0 to the angle list.")

    sock.close()  # Socket'i kapat

# Ana program
def run_udp_threads():
    # Sinüs sinyali gönderimi
    send_thread = threading.Thread(target=send_sinusoidal_signal, args=(UDP_IP, SEND_PORT))
    receive_thread = threading.Thread(target=receive_data, args=(UDP_IP, RECEIVE_PORT))

    receive_thread.start()
    send_thread.start()

    return send_thread, receive_thread

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()

    # UDP iş parçacıklarını başlat
    send_thread, receive_thread = run_udp_threads()

    # GUI'yi göster
    main.show()
    sys.exit(app.exec_())



    
    """"
    
import sys
import socket
import time
import math
import threading
from PyQt5 import QtWidgets
from pyqtgraph import PlotWidget, plot  # type: ignore
import pyqtgraph as pg  # type: ignore

# UDP ayarları
UDP_IP = "127.0.0.1"
SEND_PORT = 8081  # Python'dan QT'ye veri gönderme portu
RECEIVE_PORT = 8080  # Python'un QT'den veri aldığı port
BUFFER_SIZE = 1024

# Global değişkenler
udp_period = None  # Varsayılan değer yok
sinus_period = None  # Varsayılan değer yok
stop_event = threading.Event()  # Durdurma olayı için Event
resume_event = threading.Event()  # Tekrar başlatma olayı
resume_event.set()  # Başlangıçta devam etmeye ayarlı

# Açı değerlerini saklayacak listeler
received_angles_8080 = []  # 8080 portundan alınan açı değerleri
sent_angles_8081 = []  # 8081 portuna gönderilen açı değerleri

# PyQt5 arayüzü
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # Arayüz ayarları
        self.setWindowTitle("Rocket kanatçık Simulation")

        # İki adet grafik penceresi oluştur
        self.graphWidget1 = pg.PlotWidget()
        self.graphWidget2 = pg.PlotWidget()

        # İlk grafiği yerleştir (8080'den alınan açılar)
        self.graphWidget1.setTitle("8080 Portundan Alınan Açılar")
        self.graphWidget1.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget1.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget1.setYRange(-180, 180)

        # İkinci grafiği yerleştir (8081'e gönderilen sinüs değerleri)
        self.graphWidget2.setTitle("8081 Portuna Gönderilen Sinüs Sinyalleri")
        self.graphWidget2.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget2.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget2.setYRange(-180, 180)

        # Ana widget ayarları
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.graphWidget1)
        layout.addWidget(self.graphWidget2)

        # Merkezi widget ayarla
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Gerçek zamanlı veri güncelleme için zamanlayıcı
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)  # 100 ms'de bir grafik güncellemesi

    def update_plots(self):
        # 8080'den alınan açı değerlerini çizdir
        self.graphWidget1.plot(received_angles_8080, pen=pg.mkPen(color='b'), clear=True)

        # 8081'e gönderilen sinüs değerlerini çizdir
        self.graphWidget2.plot(sent_angles_8081, pen=pg.mkPen(color='r'), clear=True)

# Sinüs sinyali gönderimi için fonksiyon
def send_sinusoidal_signal(ip, port):
    global sinus_period, udp_period, stop_event, resume_event, sent_angles_8081
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.time()

    while not stop_event.is_set():
        if sinus_period is not None and udp_period is not None and resume_event.is_set():
            elapsed_time = time.time() - start_time
            t = elapsed_time * 1000  # Milisaniye cinsine çevriliyor
            if sinus_period != 0:
                # Sinüs sinyalini derece cinsinden hesapla
                angle = (360 * t / sinus_period) % 360
                # Sinüs sinyalini -180 ile +180 arasında hesapla
                sinus_value = int(round(math.sin(math.radians(angle)) * 180))
                # -180 ile +180 arasında sınırlama yap
                sinus_value = max(-180, min(180, sinus_value))
            else:
                sinus_value = 0  # Eğer periyot sıfırsa sinüs sinyali 0 olur

            message = str(sinus_value).encode()  # Açı cinsinden integer olarak gönder
            sock.sendto(message, (ip, port))
            print(f"Sent sinusoidal value: {sinus_value}")

            # Gönderilen açı değerini kaydet
            sent_angles_8081.append(sinus_value)
            if len(sent_angles_8081) > 100:  # Sadece son 100 değeri sakla
                sent_angles_8081.pop(0)

            time.sleep(udp_period / 1000.0)  # UDP periyoduna göre sinyal gönderiliyor
        else:
            print("Waiting for UDP period and sinus period settings or communication stopped.")
            time.sleep(1)  # Ayarların gelmesini beklemek için bekleme süresi

    sock.close()  # Socket'i kapat

# Veri alma ve parametreleri ayarlama fonksiyonu
def receive_data(ip, port):
    global udp_period, sinus_period, stop_event, resume_event, received_angles_8080
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))

    last_received_time = time.time()  # Son veri alınma zamanı
    
    while not stop_event.is_set():
        sock.settimeout(1.0)  # 1 saniyelik zaman aşımı
        try:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            decoded_data = data.decode().strip()  # Gelen veri decode edilip boşluklar temizleniyor
            print(f"Received data: {decoded_data}")

            last_received_time = time.time()  # Veri alındığında zamanı güncelle

            try:
                angle_value = int(decoded_data)
                # Gelen açı değerini kaydet
                received_angles_8080.append(angle_value)
                if len(received_angles_8080) > 100:  # Sadece son 100 değeri sakla
                    received_angles_8080.pop(0)

            except ValueError:
                # Veri iki parçaya ayrılıyor
                data_parts = decoded_data.split(',')
                if len(data_parts) == 2:
                    try:
                        udp_period = int(data_parts[0])  # İlk veri: UDP veri gönderme periyodu (milisaniye)
                        sinus_period = int(data_parts[1])  # İkinci veri: Sinüs sinyalinin periyodu (milisaniye)
                        print(f"UDP period set to: {udp_period}, Sinus period set to: {sinus_period}")
                        resume_event.set()  # Yeni veri geldiğinde sinyali tekrar başlat
                    except ValueError:
                        print(f"Invalid data received: {decoded_data}")  # Hatalı veri varsa göster
                        stop_event.set()  # Hata durumunda durdurma olayını işaretle
                else:
                    if decoded_data == "UDP communication stopped.":
                        print("UDP communication stopped.")
                        resume_event.clear()  # Sinyal gönderimini durdur
                    else:
                        print("Data format is incorrect. Expected two values separated by a comma.")
        except socket.timeout:
            # Zaman aşımı durumunda, veri gelmediğinde 0 ekle
            elapsed_since_last_received = time.time() - last_received_time
            if elapsed_since_last_received >= 1.0:  # 1 saniyede veri gelmediyse 0 ekle
                received_angles_8080.append(0)
                if len(received_angles_8080) > 100:  # Sadece son 100 değeri sakla
                    received_angles_8080.pop(0)
                print("No data received, appending 0 to the angle list.")

    sock.close()  # Socket'i kapat

# Ana program
def run_udp_threads():
    # Sinüs sinyali gönderimi
    send_thread = threading.Thread(target=send_sinusoidal_signal, args=(UDP_IP, SEND_PORT))
    receive_thread = threading.Thread(target=receive_data, args=(UDP_IP, RECEIVE_PORT))

    receive_thread.start()
    send_thread.start()

    return send_thread, receive_thread

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()

    # UDP iş parçacıklarını başlat
    send_thread, receive_thread = run_udp_threads()

    # GUI'yi göster
    main.show()
    sys.exit(app.exec_())
    
    
    
    
    
    ----------------------------------------------
    
    
    
    
    
    
import sys
import socket
import time
import math
import threading
from PyQt5 import QtWidgets
from pyqtgraph import PlotWidget, plot # type: ignore
import pyqtgraph as pg # type: ignore

# UDP ayarlari
UDP_IP = "127.0.0.1"
SEND_PORT = 8081  # Python'dan QT'ye veri gonderme portu
RECEIVE_PORT = 8080  # Python'un QT'den veri aldigi port
BUFFER_SIZE = 1024

# Global degiskenler
udp_period = None  # Varsayilan deger yok
sinus_period = None  # Varsayilan deger yok
stop_event = threading.Event()  # Durdurma olayi icin Event

# Açı değerlerini saklayacak listeler
received_angles_8080 = []  # 8080 portundan alınan açı değerleri
sent_angles_8081 = []  # 8081 portuna gönderilen açı değerleri

# PyQt5 arayüzü
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # Arayüz ayarları
        self.setWindowTitle("Rocket kanatçık Simulation")

        # İki adet grafik penceresi oluştur
        self.graphWidget1 = pg.PlotWidget()
        self.graphWidget2 = pg.PlotWidget()

        # İlk grafiği yerleştir (8080'den alınan açılar)
        self.graphWidget1.setTitle("8080 Portundan Alınan Açılar")
        self.graphWidget1.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget1.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget1.setYRange(-180, 180)

        # İkinci grafiği yerleştir (8081'e gönderilen sinüs değerleri)
        self.graphWidget2.setTitle("8081 Portuna Gönderilen Sinüs Sinyalleri")
        self.graphWidget2.setLabel('left', 'Açı Değeri (Derece)')
        self.graphWidget2.setLabel('bottom', 'Zaman (Saniye)')
        self.graphWidget2.setYRange(-180, 180)

        # Ana widget ayarları
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.graphWidget1)
        layout.addWidget(self.graphWidget2)

        # Merkezi widget ayarla
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Gerçek zamanlı veri güncelleme için zamanlayıcı
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(100)  # 100 ms'de bir grafik güncellemesi

    def update_plots(self):
        # 8080'den alınan açı değerlerini çizdir
        self.graphWidget1.plot(received_angles_8080, pen=pg.mkPen(color='b'), clear=True)

        # 8081'e gönderilen sinüs değerlerini çizdir
        self.graphWidget2.plot(sent_angles_8081, pen=pg.mkPen(color='r'), clear=True)

# Sinüs sinyali gönderimi için fonksiyon
def send_sinusoidal_signal(ip, port):
    global sinus_period, udp_period, stop_event, sent_angles_8081
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_time = time.time()

    while not stop_event.is_set():
        if sinus_period is not None and udp_period is not None:
            elapsed_time = time.time() - start_time
            t = elapsed_time * 1000  # Milisaniye cinsine çevriliyor
            if sinus_period != 0:
                # Sinüs sinyalini derece cinsinden hesapla
                angle = (360 * t / sinus_period) % 360
                # Sinüs sinyalini -180 ile +180 arasında hesapla
                sinus_value = int(round(math.sin(math.radians(angle)) * 180))
                # -180 ile +180 arasında sınırlama yap
                sinus_value = max(-180, min(180, sinus_value))
            else:
                sinus_value = 0  # Eğer period sıfırsa sinüs sinyali 0 olur
            
            message = str(sinus_value).encode()  # Açı cinsinden integer olarak gönder
            sock.sendto(message, (ip, port))
            print(f"Sent sinusoidal value: {sinus_value}")

            # Gönderilen açı değerini kaydet
            sent_angles_8081.append(sinus_value)
            if len(sent_angles_8081) > 100:  # Sadece son 100 değeri sakla
                sent_angles_8081.pop(0)

            time.sleep(udp_period / 1000.0)  # UDP periyoduna göre sinyal gönderiliyor
        else:
            print("Waiting for UDP period and sinus period settings.")
            time.sleep(1)  # Ayarların gelmesini beklemek için bekleme süresi

    sock.close()  # Socket'i kapat

# Veri alma ve parametreleri ayarlama fonksiyonu
def receive_data(ip, port):
    global udp_period, sinus_period, stop_event, received_angles_8080
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    
    while not stop_event.is_set():
        data, addr = sock.recvfrom(BUFFER_SIZE)
        decoded_data = data.decode().strip()  # Gelen veri decode edilip boşluklar temizleniyor
        print(f"Received data: {decoded_data}")

        try:
            angle_value = int(decoded_data)
            # Gelen açı değerini kaydet
            received_angles_8080.append(angle_value)
            if len(received_angles_8080) > 100:  # Sadece son 100 değeri sakla
                received_angles_8080.pop(0)

        except ValueError:
            # Veri iki parçaya ayrılıyor
            data_parts = decoded_data.split(',')
            if len(data_parts) == 2:
                try:
                    udp_period = int(data_parts[0])  # İlk veri: UDP veri gönderme periyodu (milisaniye)
                    sinus_period = int(data_parts[1])  # İkinci veri: Sinüs sinyalinin periyodu (milisaniye)
                    print(f"UDP period set to: {udp_period}, Sinus period set to: {sinus_period}")
                except ValueError:
                    print(f"Invalid data received: {decoded_data}")  # Hatalı veri varsa göster
                    stop_event.set()  # Hata durumunda durdurma olayını işaretle
            else:
                if decoded_data == "UDP communication stopped.":
                    print("UDP communication stopped.")
                    stop_event.set()  # Hata durumunda durdurma olayını işaretle
                else:
                    print("Data format is incorrect. Expected two values separated by a comma.")

    sock.close()  # Socket'i kapat

# Ana program
def run_udp_threads():
    # Sinüs sinyali gönderimi
    send_thread = threading.Thread(target=send_sinusoidal_signal, args=(UDP_IP, SEND_PORT))
    receive_thread = threading.Thread(target=receive_data, args=(UDP_IP, RECEIVE_PORT))

    receive_thread.start()
    send_thread.start()

    return send_thread, receive_thread

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()

    # UDP iş parçacıklarını başlat
    send_thread, receive_thread = run_udp_threads()

    # GUI'yi göster
    main.show()
    sys.exit(app.exec_())
    
    """
