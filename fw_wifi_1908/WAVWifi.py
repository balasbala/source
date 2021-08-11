import ujson
import json
import network
from network import WLAN
import machine
import socket
import usocket as socket
import gc
gc.collect()

class WAVWireless():
    def __init__(self):
        self.filename = "wifiap.json"
        self.wifiCfg = self.reload()
        self.sta_if = network.WLAN(network.STA_IF)
        self.sta_if.active(True)
        self.wlan = WLAN(network.STA_IF)
        self.led = machine.Pin(2, machine.Pin.OUT)
        
    def reloadCfg(self):
        self.wifiCfg = self.reload()
        
    def reload(self):
        list = []
        with open(self.filename) as fp:
            while True:
                res = []
                d = {}
                data = fp.readline()
                if data == '':
                    fp.close()
                    break
                apdata = ujson.dumps(data)
                data = data.replace("\r\n", "")
                for sub in data.split(','):
                    if ':' in sub:
                        res = sub.split(':', 1)
                        print(res)
                        d[res[0]] = res[1]
                list.append(d)
            return list
        
    def scanAndConnect(self):
        self.conn = 0
        if not self.sta_if.isconnected():
            self.sta_if.active(True)
            nets = self.wlan.scan()
            for net in nets:
                for i in range(len(self.wifiCfg)):
                    ssid = net[0].decode('ASCII')
                    print(ssid)
                    print(self.wifiCfg[i]['wifiap'])
                    if ssid == self.wifiCfg[i]['wifiap']:
                        print(ssid)
                        print(self.wifiCfg[i]['password'])
                        password = (self.wifiCfg[i]['password'])
                        self.wlan.connect(ssid, password)
                        while not self.wlan.isconnected():
                         machine.idle()      
                        print('WLAN connection successful')
                        print(self.wlan.ifconfig())
                        return True
            return False
        
    def webpage(self):
        
         if self.led.value() == 1:
           gpio_state="ON"
         else:
           gpio_state="OFF"
        
         html = """<html><head> <title>ESP Web Server</title> <meta name="viewport" content="width=device-width, initial-scale=1">
         <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
         h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
         border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
         .button2{background-color: #4286f4;}</style></head><body> <h1>ESP Web Server</h1> 
         <p>GPIO state: <strong>""" + gpio_state + """</strong></p><p><a href="/?led=on"><button class="button">ON</button></a></p>
         <p><a href="/?led=off"><button class="button button2">OFF</button></a></p></body></html>"""
         return html
        
    def startWebServer(self):    
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
           if sloc > 0 and sloc < 50:
               s = request[sloc:]
               print(s)
           conn.send('HTTP/1.1 200 OK\n')
           conn.send('Content-Type: text/html\n')
           conn.send('Connection: close\n\n')
           conn.sendall("OK")
           conn.close()
         
    
 
        

        

