# Clean Box Bluetooth Low Energy Firmware Application.
#

import bluetooth
import random
import struct
import time
from ble_advertising import advertising_payload
from machine import Pin
from micropython import const
from WAVWifi import WAVWireless
import machine
import socket
import usocket as socket
import _thread

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(4)

_CLEANBOX_UUID = bluetooth.UUID('FE400000-B5A3-F393-E0A9-E50E24DCCA9E')
_LOCK_CHAR = (bluetooth.UUID('FE400001-B5A3-F393-E0A9-E50E24DCCA9E'), bluetooth.FLAG_WRITE | bluetooth.FLAG_READ,)
_OZONE_CHAR = (bluetooth.UUID('FE400002-B5A3-F393-E0A9-E50E24DCCA9E'), bluetooth.FLAG_WRITE | bluetooth.FLAG_READ,)
_DITIME_CHAR = (bluetooth.UUID('FE400003-B5A3-F393-E0A9-E50E24DCCA9E'), bluetooth.FLAG_WRITE | bluetooth.FLAG_READ,)
_BOXSTAT_CHAR = (bluetooth.UUID('FE400004-B5A3-F393-E0A9-E50E24DCCA9E'), bluetooth.FLAG_NOTIFY,)
_WIFICFG_CHAR = (bluetooth.UUID('FE400005-B5A3-F393-E0A9-E50E24DCCA9E'), bluetooth.FLAG_WRITE | bluetooth.FLAG_READ,)

_CLEANBOX_SERVICE = ( _CLEANBOX_UUID, (_LOCK_CHAR, _OZONE_CHAR, _DITIME_CHAR, _BOXSTAT_CHAR, _WIFICFG_CHAR,), )

SERVICES = ( _CLEANBOX_SERVICE, )

# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_COMPUTER = const(128)


class CleanBox:
    def __init__(self, ble, name="WAVDisinfect"):
        self._ble = ble
        self.conn_handle = 0
        self.ditime = 0
        self._ble.active(True)
        self._ble.irq(handler=self._irq)
        self.p2 = Pin(2, Pin.OUT, 1)
        self.p2.value(0)
        self.p32 = Pin(32, Pin.OUT, 1)
        self.p32.value(0)
        self._buffer = bytearray()
        self.lock_open = False
        ((self._lock_handle,self._ozone_handle, self.ditime_handle, self.status_handle, self.wificfg_handle,),) = self._ble.gatts_register_services(SERVICES)
        self._connections = set()
        #, appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER
        # , services=[_CLEANBOX_UUID]
        self._payload = advertising_payload(
            name=name, appearance = _ADV_APPEARANCE_GENERIC_COMPUTER
        )
        self._advertise()

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        print('event {}'.format(event))
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _, = data
            self._connections.add(conn_handle)
            self.conn_handle = conn_handle
            self._ble.gatts_write(self.wificfg_handle, bytes(100))
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _, = data
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
            self.conn_handle = conn_handle
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            print('GATTS Write')
            if conn_handle in self._connections:
                print('conn handle in connections')
            if value_handle == self._lock_handle:
                print('Lock Handle')
            if value_handle == self._ozone_handle:
                print('Ozone Handle')
            if conn_handle in self._connections and value_handle == self._lock_handle:
                print('GATTS Write Lock')
                self._buffer = self._ble.gatts_read(self._lock_handle)
                print('buffer: {}'.format(self._buffer[0]))
                if self._buffer[0] == 0:
                    self.lock_open = True
                    self.p2.value(1)
                else:
                    self.lock_open = False
                    self.p2.value(0)
            elif conn_handle in self._connections and value_handle == self._ozone_handle:
                print('GATTS Write OZONE')
                self._buffer = self._ble.gatts_read(self._ozone_handle)
                print('buffer: {}'.format(self._buffer[0]))
                if self._buffer[0] == 0:
                    self.p32.value(1)
                else:
                    self.p32.value(0)
            elif conn_handle in self._connections and value_handle == self.ditime_handle:
                self._buffer = self._ble.gatts_read(self.ditime_handle)
                print(self._buffer)
                if len(self._buffer) == 5:
                    if self._buffer[0] == 4 and self._buffer[1] == 7 and self._buffer[2] == 9 and self._buffer[3] == 0:
                        self.ditime = self._buffer[4]
            elif conn_handle in self._connections and value_handle == self.wificfg_handle:
                self._buffer = self._ble.gatts_read(self.wificfg_handle)
                print('Wireless Config')
                print(self._buffer)
                str = self._buffer.decode("utf-8")
                with open("wifiap.json", "w") as fp:
                    res = str.split(':')
                    fdata = "wifiap:"+res[0]+",password:"+res[1]
                    print(fdata)
                    fp.write(fdata)
                    fp.close()
                
                print(res[0])
                self._ble.gatts_write(self.wificfg_handle, res[0])
                
    def _advertise(self, interval_us=500000):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)


def cleanbox():
    ble = bluetooth.BLE()
    cbox = CleanBox(ble)

    t = 25
    i = 0

    while True:
        time.sleep_ms(1000)
        if cbox.lock_open == True:
            print('lock opened')
            try:
                notify_buf = bytearray(b'\x01\x00')
                cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
            except Exception:
                print('Exception on notifying the status')
            time.sleep(60)
            print('ozone is activated')
            try:
                notify_buf = bytearray(b'\x01\x01')
                cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
            except Exception:
                print('Exception on notifying the status')
            cbox.p32.value(1)
            time.sleep(180)
            print('ozone is deactivated')
            cbox.p32.value(0)
            cbox.p2.value(0)
            cbox.lock_open = False
            print('lock closed')
            try:
                notify_buf = bytearray(b'\x00\x00')
                cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
            except Exception:
                print('Exception on notifying the status')
        elif cbox.ditime != 0:
            print('ozone is activated')
            cbox.p32.value(1)
            try:
                notify_buf = bytearray(b'\x00\x01')
                cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
            except Exception:
                print('Exception on notifying the status')
            ditime = 0
            while ditime < (60 * cbox.ditime):
                time.sleep(1)
                ditime = ditime + 1
            cbox.p32.value(0)
            cbox.ditime = 0
            print('lock closed')
            try:
                notify_buf = bytearray(b'\x00\x00')
                cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
            except Exception:
                print('Exception on notifying the status')            

def threadFunction():
    print('ozone is activated')
    global cbox
    cbox.p32.value(1)
    global dt
    try:
        notify_buf = bytearray(b'\x00\x01')
        cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
    except Exception:
        print('Exception on notifying the status')
    ditime = 0
    while ditime < (60 * dt):
        time.sleep(1)
        ditime = ditime + 1
    cbox.p32.value(0)
    cbox.ditime = 0
    print('lock closed')
    try:
        notify_buf = bytearray(b'\x00\x00')
        cbox._ble.gatts_notify(cbox.conn_handle, cbox.status_handle, notify_buf)
    except Exception:
        print('Exception on notifying the status')            
    
def wavdisinfect():
    global cbox
    ble = bluetooth.BLE()
    cbox = CleanBox(ble)
    w = WAVWireless()
    w.scanAndConnect()
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        
    s = socket.socket()
    s.bind(addr)
    s.listen(5)

    print('listening on', addr)
     
    while True:
        conn, addr = s.accept()
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        request = str(request)
        print('Content = %s' % request)
        sloc = request.find('/?dtime=')
        print(sloc)
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall("OK")
        conn.close()
        if sloc > 0 and sloc < 50:
            sub = request[sloc:]
            ss = sub.split(' ')
            global dt
            dt = int(ss[0].replace("/?dtime=",""))
            if dt > 0:            
                _thread.start_new_thread(threadFunction, ())
            else:
                cbox.p32.value(0)
                dt = 0
if __name__ == "__main__":
    wavdisinfect()