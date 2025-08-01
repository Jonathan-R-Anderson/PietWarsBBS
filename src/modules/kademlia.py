import logging
import hashlib
import socks
import socket
import stem.process
import stem.socket
import threading
import config
import json
import random
import string


logging.basicConfig(filename='/debug/piet_wars.log', level=logging.INFO)  # Change the filename as needed

class KademliaNode:
    def __init__(self, node_id, address, port):
        logging.info("Initializing KademliaNode.")
        self.node_id = node_id
        self.address = address
        self.port = int(port)  # Added port attribute
        self.data_store = {}

    def __str__(self):
        return f"{self.address}:{self.port}"

    def __eq__(self, other):
        """Override the equality comparison."""
        if isinstance(other, KademliaNode):
            return (
                self.node_id == other.node_id and
                self.address == other.address and
                self.port == other.port
            )
        return False

    def __hash__(self):
        """Override the hash calculation."""
        return hash((self.node_id, self.address, self.port))

class KademliaDHT:
    def __init__(self):
        logging.info("Initializing KademliaDHT.")
        self.local_onion_address = None
        self.local_port = None
        self.local_node = None
        self.nodes = None
        self.routing_table = [[] for _ in range(160)]  # Initialize routing table with empty buckets
        logging.info("KademliaDHT initialized.")

    def initialize_node(self):
        logging.info("Initializing local node.")
        if (self.local_onion_address is not None and 
            self.local_port is not None):
            self.local_node = KademliaNode(self._get_node_id(self.local_onion_address), self.local_onion_address, self.local_port)
            self.nodes = {self.local_node.node_id: self.local_node}  # Store local node as the root node
            self.routing_table[self._get_bucket_index(self.local_node.node_id)].append(self.local_node)  # Add local node to appropriate bucket
            logging.info("Local node initialized.")

    def set_local_onion_address(self, local_onion_address):
        logging.info("Setting local onion address.")
        self.local_onion_address = local_onion_address

    def set_local_port(self, local_port):
        logging.info("Setting local port.")
        self.local_port = local_port

    def _get_bucket_index(self, node_id):
        distance = int(node_id, 16) ^ int(self.local_node.node_id, 16)
        return distance.bit_length() - 1  # Calculate index of the appropriate bucket

    def find_closest_nodes(self, target_node_id, count):
        bucket_index = self._get_bucket_index(target_node_id)
        closest_nodes = []
        for node in self.routing_table[bucket_index]:
            closest_nodes.append(node)
            if len(closest_nodes) == count:
                break
        return closest_nodes

    def store(self, key, value):
        logging.info("Storing key-value pair.")
        node_id = self._get_node_id(key)
        closest_nodes = self.find_closest_nodes(node_id, K)
        for node in closest_nodes:
            node.data_store[key] = value

    def retrieve(self, key):
        logging.info("Retrieving value for key.")
        node_id = self._get_node_id(key)
        closest_nodes = self.find_closest_nodes(node_id, K)
        for node in closest_nodes:
            if key in node.data_store:
                return node.data_store[key]
        return None

    def list_players(self):
        logging.info("Listing all players in the DHT.")

        # Initialize an empty list to store all players
        all_players = []

        # Iterate through each bucket in the routing table
        for bucket in self.routing_table:
            # Iterate through each node in the bucket and add it to the list of players
            for node in bucket:
                if (node.address != self.local_onion_address):
                    all_players.append(node)  # Modified to store address and port
        all_players = list(set(all_players))
        return all_players

    def _get_node_id(self, onion_address):
        logging.info("Calculating node ID from onion address.")
        return hashlib.sha1(onion_address.encode()).hexdigest()
    
    def send_payload(self, peer_hidden_address, peer_port, payload):
        logging.info(f"Attempting to send {payload}")
        logging.info("Setting up SOCKS proxy")
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)

        logging.info("Setting socket to SOCKS")
        socket.socket = socks.socksocket

        logging.info("Creating socket")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logging.info(f"Connecting to {peer_hidden_address}:{peer_port} type {type(peer_port)}")
        s.connect((peer_hidden_address, peer_port))

        logging.info(f"Sending payload {payload}")
        s.sendall(payload)

        logging.info("Payload sent successfully")
        return s
    
    def _perform_handshake(self, peer_hidden_address, peer_port):
        try:
            # Establish a SOCKS connection using Stem
            socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)
            socket.socket = socks.socksocket
            
            # Create a socket to connect to the peer's Tor hidden service
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Connect to the peer's Tor hidden service
                s.connect((peer_hidden_address, peer_port))

                # Send the originator's Tor hidden address and port as part of the handshake
                handshake_request = {
                    "type": "handshake",
                    "address": self.local_node.address,  # Originator's Tor hidden address
                    "port": self.local_node.port  # Originator's port
                }
                payload = f"BEGIN{json.dumps(handshake_request)}END".encode()
                s.sendall(payload)

                # Return the socket
                return s
        except Exception as e:
            logging.error(f"Handshake with peer failed. Error: {e}")
            return None

    def _request_peer_list(self, bootstrap_node_hidden_address, bootstrap_node_port):
        try:
            # Perform handshake with the bootstrap node to obtain a socket
            peer_socket = self._perform_handshake(bootstrap_node_hidden_address, bootstrap_node_port)
            
            if peer_socket:
                # Send command to request peer list
                request = {"type": "peer_list_request", 
                           "address": self.local_node.address,  # Originator's Tor hidden address
                            "port": self.local_node.port}
                payload = f"BEGIN{json.dumps(request)}END".encode()
                peer_socket.sendall(payload)

                # Receive and parse the peer list response
                response_data = peer_socket.recv(1024).decode()
                response = json.loads(response_data)

                if response.get("type") == "peer_list_response":
                    peer_list = response.get("peers", [])
                    return [KademliaNode(node.get("node_id"), node.get("address"), node.get("port")) for node in peer_list]
                else:
                    return []
            else:
                return []
        except Exception as e:
            logging.error(f"Failed to request peer list from node. Error: {e}")
            return []
        
    def join_network(self, known_node_address, known_node_port):
        # Step 1: Perform handshake with the known node to obtain its peer list
        peer_list = self._request_peer_list(known_node_address, known_node_port)

        if peer_list:
            # Step 2: Request peer list from peers returned by the known node
            for peer_node in peer_list:
                self._request_peer_list(peer_node.address, peer_node.port)

    def launch_dns_all_interfaces(self, port, stdscr):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(('0.0.0.0', port))
            server_socket.listen(5)
            logging.info("Server is listening on {}:{}".format('0.0.0.0', port))

            while True:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self.handle_received_data, args=(client_socket,)).start()
        
        except Exception as e:
            logging.error(f"Error in launch_dns_all_interfaces: {e}")

    def launch_onion_server(self, port,stdscr):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(('127.0.0.1', port))
            server_socket.listen(5)
            logging.info("Server is listening on {}:{}".format('127.0.0.1', port))

            while True:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self.handle_received_data, args=(client_socket,)).start()

        except Exception as e:
            logging.error(f"Error in launch_dns_local_interface: {e}")

    def is_game_configured(self):
        chosen_game = config.PLAYERS[config.CHOSEN_GAME]
        return chosen_game.get("time_limit") and chosen_game.get("max_players") and chosen_game.get("flag") and chosen_game.get("player_color")

    def set_session_info(self, sender_address, sender_port):
        logging.info("Received request for game session info")
        if config.CHOSEN_GAME is not None and config.CHOSEN_GAME < len(config.PLAYERS):
            game = config.PLAYERS[config.CHOSEN_GAME]
            logging.info(f"GAME, {game}, {type(game)}")
            configs = game.get("configs", "")
            players = game.get("players", "")
            session_info = {"type": "SETSESSIONINFO", "address": game["address"], "port": game["port"], "value": {"configs":configs, "players":players}}
            session_json = json.dumps(session_info)
            session_query = f"BEGIN{session_json}END".encode()
            self.send_payload(sender_address, sender_port, session_query)
        else:
            logging.warning("No chosen game or invalid game index")

    def get_session_info(self, sender_address, sender_port, parsed_data):
        parsed_data["type"] = "game_invitation"
        logging.info(f"Possibly saving parsed data to config.PLAYERS {parsed_data}")
        if (parsed_data not in config.PLAYERS):
            config.PLAYERS.append(parsed_data)
        session_info = {"type": "GETSESSIONINFO", "address": self.local_onion_address, "port": self.local_port}
        session_json = json.dumps(session_info)
        session_query = f"BEGIN{session_json}END".encode()
        self.send_payload(sender_address, sender_port, session_query)


    def save_session_info(self, sender_address, sender_port, parsed_data):
        # Ensure the 'players' key exists in parsed_data
        players = parsed_data.get("value", {}).get("players", {})

        # Check if the game invitation already exists
        existing_game = next((invite for invite in config.PLAYERS if invite['address'] == sender_address and invite['port'] == sender_port), None)
        
        if existing_game:
            # Update existing game's player list
            existing_game["players"].update(players)
        else:
            # Create a new game invitation if it doesn't exist
            invitation = {
                "type": "game_invitation",
                "address": sender_address,
                "port": sender_port,
                "players": players if players else {sender_address: {}}
            }
            config.PLAYERS.append(invitation)


    def set_client_wait_for_game(self, sender_address, sender_port):
        logging.info("Received acceptance of game invitation")
        # Store the new player's information in the 'players' dictionary
        config.CHOSEN_GAME = 0    
        session_info = {"type": "WAITINGFORGAME",
                        "address": self.local_node.address,
                        "port": self.local_node.port}
        session_info = json.dumps(session_info)
        session_info = f"BEGIN{session_info}END".encode()
        logging.info(f"Created session info: {session_info}")
        self.send_payload(sender_address, sender_port, session_info)
        logging.info("Sent payload to player")

    def get_board_status(self, target_address, target_port):
        board_info = {"type": "GETBOARDSTATUS",
                "address": self.local_node.address,
                "port": self.local_node.port,
                "grid": config.PLAYERS[0].get("players").get(self.local_onion_address)
                }
        board_info = json.dumps(board_info)
        board_info = f"BEGIN{board_info}END".encode()
        logging.info(f"Created session info: {board_info}")
        self.send_payload(target_address, target_port, board_info)
        logging.info("Sent payload to player")     


    def update_board(self, target_address, target_port, parsed_data):
        logging.info(f"RECEIVED BOARD UPDATE {parsed_data}")

    def set_host_wait_for_game(self, sender_address, parsed_data):
        config.GAME_STATUS = 0
        logging.info(f"Attempting to add parsed data to players: {config.PLAYERS[config.CHOSEN_GAME]} at chosen game: {config.CHOSEN_GAME}")
        if not config.PLAYERS[config.CHOSEN_GAME].get("players"):
            config.PLAYERS[config.CHOSEN_GAME]["players"] = {sender_address : {}}
            config.PLAYERS[config.CHOSEN_GAME]["players"][sender_address] = parsed_data
        else:
            config.PLAYERS[config.CHOSEN_GAME]["players"][sender_address] = parsed_data
        logging.info("Setting computer into wait mode")
        logging.info(f"Players so far: {config.PLAYERS[config.CHOSEN_GAME]}")

    def set_host_start_game(self):
        config.GAME_STATUS = 1
        logging.info("Setting game status as starting")

    def get_bootstrap_nodes(self, client_socket):
        logging.info("Received list_bootstrap")
        # Get the list of peers
        peers = [str(p) for p in config.DHT.list_players()]

        # Convert the list of peers to JSON format
        peer_list_json = json.dumps({"peers": peers})

        response = f"BEGIN{peer_list_json}END"
        logging.info(f"Sending {response}")

        # Send the JSON response back to the client
        client_socket.sendall(response.encode())  

    def handle_received_data(self, client_socket):
        logging.info("Starting to handle received data")
        data = b""
        while not data.endswith(b"END"):
            data += client_socket.recv(1)
        data = data.decode()
        try:
            parsed_data = json.loads(data.strip("BEGIN").strip("END"))
            logging.info(f"Parsing received data: {parsed_data}")
            data_type = parsed_data.get("type")
            sender_address = parsed_data.get("address")
            sender_port = parsed_data.get("port")
            if sender_address is not None and sender_port is not None:
                logging.info("Peer information found, creating Kademlia node")
                peer = KademliaNode(self._get_node_id(sender_address), sender_address, sender_port)
                self._add_to_routing_table(peer)
                if data_type == "game_invitation":
                    self.get_session_info(sender_address, sender_port, parsed_data)

                elif data_type == "GETSESSIONINFO":
                    self.set_session_info(sender_address, sender_port)

                elif data_type == "SETSESSIONINFO":
                    self.save_session_info(sender_address, sender_port, parsed_data)

                elif data_type == "AcceptInvite":
                    self.set_client_wait_for_game(sender_address, sender_port)

                elif data_type == "WAITINGFORGAME":                
                    self.set_host_wait_for_game(sender_address, parsed_data)

                elif data_type == "STARTGAME":
                    self.set_host_start_game()
                    
                elif data_type == "DeclineInvite":
                    logging.info("Received decline of game invitation")
                    # Do nothing

                elif data_type == "list_bootstrap":
                    self.get_bootstrap_nodes(client_socket)

                elif data_type == "GETBOARDSTATUS":
                    self.update_board(self, sender_address, sender_port, parsed_data)
                
                elif data_type == "SETBOARDSTATUS":
                    self.get_board_status(self, sender_address, sender_port)

                else:
                    logging.info(f"Received unknown command {parsed_data}")
            else:
                logging.warning(f"Received status data for unknown player: {sender_address}")
        except json.JSONDecodeError as e:
            logging.error(f"{data}: JSON decoding error - {str(e)}")



    def bootstrap(self, bootstrap_address, bootstrap_port):
        # Check if the provided address is an onion address
        if bootstrap_address.endswith('.onion'):
            peers = self.join_network(bootstrap_address, bootstrap_port)
            for peer in peers:
                peer = peer.split(":")
                peer_address = peer[0]
                peer_port = peer[1]
                logging.info(f"Adding peer {peer}")
                peer = KademliaNode(self._get_node_id(peer_address), peer_address, peer_port)
                self._add_to_routing_table(peer)
        else:
            # Connect to bootstrap.breached.computer at port 1337 to get a list of peers
            peers = self._connect_to_bootstrap_server(bootstrap_address, bootstrap_port)
            print("peers", peers)
            for peer in peers:
                peer = peer.split(":")
                peer_address = peer[0]
                peer_port = peer[1]
                logging.info(f"Adding peer {peer}")
                peer = KademliaNode(self._get_node_id(peer_address), peer_address, peer_port)
                self._add_to_routing_table(peer)
                
    def _connect_to_bootstrap_server(self, bootstrap_address, bootstrap_port):
        peer_list = []

        try:
            # Set up SOCKS proxy
            socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)
            socket.socket = socks.socksocket

            # Create a socket to connect to the peer's Tor hidden service
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                logging.info(f"Connecting to {bootstrap_address}:{bootstrap_port}")

                # Connect to the peer's Tor hidden service
                s.connect((bootstrap_address, bootstrap_port))
                
                logging.info("Connected successfully")

                # Send the handshake request
                handshake_request = {"type": "list_bootstrap", 
                                    "address": self.local_node.address, 
                                    "port": self.local_node.port}
                payload = f"BEGIN{json.dumps(handshake_request)}END".encode()   
                s.sendall(payload)

                logging.info("Payload sent successfully")

                # Receive and parse the peer list response
                data = b""
                while not data.endswith(b"END"):
                    listener = s.recv(1)
                    data += listener
                    logging.info(f"received partial {data}")

                logging.info(f"Received data: {data}")
                
                # Decode the response and extract peer list
                data_str = data.decode().strip("BEGIN").strip("END")
                peer_data = json.loads(data_str)
                peer_list = peer_data.get("peers", [])

                # Log the received peer list
                logging.info(f"Received peer list: {peer_list}")

        except Exception as e:
            # Log any errors that occur during the connection attempt
            logging.error(f"Error connecting to bootstrap server: {e}")

        return peer_list

    def _add_to_routing_table(self, node):
        bucket_index = self._get_bucket_index(node.node_id)
        bucket = self.routing_table[bucket_index]

        if len(bucket) < 20 and node not in bucket:  # Bucket is not full
            bucket.append(node)
        else:
            # Bucket is full, perform replacement strategy (e.g., Least Recently Seen)
            # For simplicity, we'll remove the least recently seen node and add the new node
            # You can implement a more sophisticated replacement strategy as needed
            # For example, you might consider checking node liveness before replacing
            # Here, we assume that the first node in the bucket is the least recently seen
            bucket.pop(0)
            bucket.append(node)

    def _generate_chunk_id(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    def _hash_chunk(self, chunk_data):
        return hashlib.sha256(chunk_data).hexdigest()

    def _split_file_into_chunks(self, file_data):
        chunks = []
        chunk_id_list = []

        num_chunks = len(file_data) // config.CHUNK_SIZE + (1 if len(file_data) % config.CHUNK_SIZE != 0 else 0)
        for i in range(num_chunks):
            start = i * config.CHUNK_SIZE
            end = min((i + 1) * config.CHUNK_SIZE, len(file_data))
            chunk_data = file_data[start:end]
            chunk_id = self._generate_chunk_id()
            chunk_id_list.append(chunk_id)
            chunk = {
                "chunk_id": chunk_id,
                "chunk_data": chunk_data
            }
            chunks.append(chunk)

        return chunks, chunk_id_list

    def store_file(self, file_name, file_data):
        logging.info("Storing file in the DHT.")

        # Step 1: Split the file into chunks
        chunks, chunk_id_list = self._split_file_into_chunks(file_data)

        # Step 2: Store metadata about the file in the DHT
        file_metadata = {
            "file_name": file_name,
            "file_size": len(file_data),
            "chunk_ids": chunk_id_list
        }
        self.store(file_name, file_metadata)

        # Step 3: Store each chunk in the DHT
        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            chunk_data = chunk["chunk_data"]
            chunk_hash = self._hash_chunk(chunk_data)
            self.store(chunk_id, {"data": chunk_data, "hash": chunk_hash})

        logging.info("File stored successfully.")

    def retrieve_file(self, file_name):
        logging.info("Retrieving file from the DHT.")

        # Step 1: Retrieve metadata about the file from the DHT
        file_metadata = self.retrieve(file_name)

        if not file_metadata:
            logging.error("File not found in the DHT.")
            return None

        # Step 2: Retrieve each chunk of the file from the DHT
        chunks = []
        for chunk_id in file_metadata["chunk_ids"]:
            chunk_data = self.retrieve(chunk_id)
            if chunk_data:
                chunks.append(chunk_data["data"])
            else:
                logging.error(f"Chunk {chunk_id} not found in the DHT.")

        # Step 3: Reconstruct the file from the chunks
        file_data = b"".join(chunks)

        logging.info("File retrieved successfully.")
        return file_data
