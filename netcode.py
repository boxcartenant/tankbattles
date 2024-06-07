import socket
import threading
import time
import ast


WAIT_TIMEOUT = 1000 #timeout to wait for payload after receiving header.

#Usage:
#
# callbacks = {"ready":readyfunc, "unit":unitfunc, "die":diefunc,"target":targetfunc}
# myserver = ServerClient(ip,port,callbacks) #if server
# myclient = ServerClient(ip,port,callbacks) #if client
#
# myserver.start_server()
# myclient.start_client()
#
# #send something
# myserver.send(callbackname, payload)
# myclient.send(callbackname, payload)
#
# myserver.stop()
# myclient.stop()

class ServerClient:
    def __init__(self, host='localhost', port=12345, callback_dict = {}):
        self.host = host
        self.port = port
        self.callback_dict = callback_dict
        self.net_socket = None
        self.lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()

    def stop(self):
        # Turn off the server or client
        self.running.clear()
        if self.net_socket:
            self.net_socket.shutdown(socket.SHUT_RDWR)
            self.net_socket.close()
            self.net_socket = None
        print("Connection closed and thread terminated.")

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)
        print("server is listening on port", self.port)

        self.net_socket, addr = server_socket.accept()
        print(f"connection from {addr} has been established.")

        threading.Thread(target=self.handle_incoming, args=(self.net_socket,)).start()
    
    def start_client(self):
        self.net_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.net_socket.connect((self.host, self.port))
        print(f"Connected to server at {self.host}:{self.port}")
        threading.Thread(target=self.handle_incoming, args=(self.net_socket,)).start()


    def send(self, message, payload):
        #locks and sends two separate messages
        with self.lock:
            self.net_socket.send(message.encode())
            self.net_socket.send(str(payload).encode())

    def handle_incoming(self,*arrrrrgs):
        msg = None
        payload = None
        while self.running.is_set():
            msg = self.net_socket.recv(1024).decode()
            if msg:
                print("received:",msg, type(msg))
            if str(msg) in self.callback_dict.keys():
                start_time = time.time()
                payload = self.net_socket.recv(1024).decode()
                if payload:
                    print("payload:",payload)
                    try:
                        payload_data = ast.literal_eval(payload)
                    except (ValueError, SyntaxError):
                        payload_data = payload
                    self.callback_dict[msg](payload_data)
            msg = None
            payload = None

#def showpayloads(payload):
#    print(payload)
#
#testdict = {"a":showpayloads}
#myServer = ServerClient(host='localhost', port=12345, callback_dict = testdict)
#myClient = ServerClient(host='localhost', port=12345, callback_dict = testdict)
