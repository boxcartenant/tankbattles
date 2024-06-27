import socket
import threading
import queue
import time
import ast
#import pickle
import dill
from bfield_unit import net_unit_archetype
from tkinter import messagebox

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
    #this class is intended to manage exactly one server XOR one client, not both.
    def __init__(self, host='localhost', port=12345, callback_dict = {}):
        self.host = host
        self.port = port
        self.callback_dict = callback_dict
        self.net_socket = None
        self.lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()
        self.outbound_queue = queue.Queue()
        self.inbound_queue = queue.Queue()
        self.isServer = False
        self.isClient = False
        self.message_id = 0
        #self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def initialize(self, host='localhost', port=12345, callback_dict = {}):
        self.host = host
        self.port = port
        self.callback_dict = callback_dict

    def stop(self):
        # Turn off the server or client
        self.running.clear()
        self.receive_thread.join()
        self.send_thread.join()
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
        connected = False
        connectionCanceled = False
        def serverListen(self, *arrrgs):
            nonlocal connected, connectionCanceled, server_socket
            while (not connected) and (not connectionCanceled):
                try:
                    server_socket.settimeout(10)
                    self.net_socket, addr = server_socket.accept()
                    print(f"connection from {addr} has been established.")
                    connected = True
                except Exception as e:
                    print(str(e)+ ". Trying again.")
                finally:
                    server_socket.settimeout(None)
        listeningthread = threading.Thread(target=serverListen, args = (self,))
        listeningthread.start()
        while (not connected) and (not connectionCanceled):
            answer = messagebox.askyesno("Waiting for connection", f"Press 'Yes' when the client has connected, or 'No' to stop waiting.")
            if answer:
                connectionCanceled = False
            else:
                connectionCanceled = True
                break
        if connected:
            self.isServer = True
            self.receive_thread = threading.Thread(target=self.handle_incoming, args=(self.net_socket,))
            self.receive_thread.start()
            self.processing_thread = threading.Thread(target=self.process_messages)
            self.processing_thread.start()
            self.send_thread = threading.Thread(target=self.send_messages)
            self.send_thread.start()
        return connected
    
    def start_client(self):
        self.net_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.net_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024) #trying to overcome some message loss issues
        self.net_socket.connect((self.host, self.port))
        print(f"Connected to server at {self.host}:{self.port}")
        self.isClient = True
        self.receive_thread = threading.Thread(target=self.handle_incoming, args=(self.net_socket,))
        self.receive_thread.start()
        self.processing_thread = threading.Thread(target=self.process_messages)
        self.processing_thread.start()
        self.send_thread = threading.Thread(target=self.send_messages)
        self.send_thread.start()


    def send(self, message, payload):
        #locks and sends two separate messages
        with self.lock:
            self.outbound_queue.put([message,payload])

    def send_messages(self):
        while self.running.is_set():
            message = self.outbound_queue.get()
            with self.lock:
                #self.net_socket.sendall(pickle.dumps(message))
                self.net_socket.sendall(dill.dumps(message))
            time.sleep(0.01)

    def handle_incoming(self,*arrrrrgs):
        msg = None
        self.net_socket.settimeout(3)
        while self.running.is_set():
            try:
                #msg = pickle.loads(self.net_socket.recv(2048))
                msg = self.net_socket.recv(2048)
                with self.lock:
                    #there was an issue with message loss, so we're trying to process incoming as fast as possible.
                    self.inbound_queue.put(msg)
            except TimeoutError as e:
                pass
            #finally:
                #self.net_socket.settimeout(None)
            
            

    def process_messages(self):
        msg = None
        while self.running.is_set():
            try:
                msg = dill.loads(self.inbound_queue.get())
                if msg:
                    if str(msg[0]) in self.callback_dict.keys() and (len(msg) > 1):
                        #start_time = time.time()
                        callback_thread = threading.Thread(target=self.callback_dict[msg[0]], args=(msg[1],), daemon=True)
                        callback_thread.start()
                        #self.callback_dict[msg[0]](msg[1])
                msg = None
            except Exception as e:
                print("process messages error:",e)


#### for testing...
            
#def showpayloads(payload):
#    print(payload, type(payload))
#testdict = {"a":showpayloads}

#myServer = ServerClient(host='localhost', port=12345, callback_dict = testdict)
#myServer.start_server()

#myClient = ServerClient(host='localhost', port=12345, callback_dict = testdict)
#myClient.start_client()
#myunit = net_unit_archetype(x=1, y=2, team_color="red")
#myClient.send("a",myunit)
