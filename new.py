import json
import re
from neo4j import GraphDatabase
import math

# --- STEP 1: NEO4J DATABASE CONFIGURATION ---
# Replace with your Neo4j database credentials.
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "graphrag") # Using the password you provided

# --- DATA LOADING ---
# This script loads data from a file named 'en-map.json'.

class EndeavorGraph:
    """
    A class to manage the creation and querying of the Endeavor building graph.
    """
    def __init__(self, uri, user, password):
        """
        Initializes the graph manager and connects to the Neo4j database.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Successfully connected to Neo4j database.")

    def close(self):
        """
        Closes the database connection.
        """
        self.driver.close()
        print("Database connection closed.")

    # --- STEP 2: LOAD NODES INTO THE DATABASE ---
    def load_nodes_from_json(self, data):
        """
        Loads all locations from the JSON data as nodes in the graph.
        """
        with self.driver.session(database="neo4j") as session:
            # Clear the database before loading to ensure a fresh start
            session.execute_write(self._clear_database)
            print("Cleared existing database.")

            # Create the nodes and set their specific labels
            result = session.execute_write(self._create_nodes, data)
            print(f"Successfully created nodes and set {result['labels_set']} labels.")

    @staticmethod
    def _clear_database(tx):
        """Deletes all nodes and relationships."""
        tx.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _create_nodes(tx, locations):
        """
        Creates a node for each location, sets its properties, and adds a specific label.
        This approach uses two efficient queries.
        """
        # Query 1: Create all nodes with a base :Location label and set properties.
        # Storing the 'type' as a property makes the next step easy.
        node_creation_query = """
        UNWIND $locations AS loc
        MERGE (n:Location {id: loc.id})
        SET n += loc, // Set all properties from the loc map
            n.grid = loc.location.grid,
            n.space_number = loc.attributes.space_number
        """
        tx.run(node_creation_query, locations=locations)

        # Query 2: Add the specific label (e.g., :ConferenceRoom) to each node
        # based on the 'type' property. Requires APOC.
        label_addition_query = """
        MATCH (n:Location) WHERE n.type IS NOT NULL
        CALL apoc.create.addLabels(id(n), [n.type]) YIELD node
        RETURN count(node) AS labels_set
        """
        result = tx.run(label_addition_query)
        return result.single()


    # --- STEP 3: CREATE RELATIONSHIPS ---
    def create_relationships(self):
        """
        Creates meaningful relationships between the nodes to build the graph.
        """
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._create_located_on_relationships)
            print("Created :LOCATED_ON relationships.")

            session.execute_write(self._create_accessible_from_relationships)
            print("Created :ACCESSIBLE_FROM relationships.")

            nodes = session.execute_read(self._get_all_location_nodes)
            self._create_near_relationships(nodes)
            print("Created :NEAR relationships.")

    @staticmethod
    def _create_located_on_relationships(tx):
        """Connects each location to a Level node."""
        query = """
        MATCH (loc:Location)
        WHERE loc.level IS NOT NULL
        MERGE (lvl:Level {number: loc.level})
        MERGE (loc)-[:LOCATED_ON]->(lvl)
        """
        tx.run(query)

    @staticmethod
    def _create_accessible_from_relationships(tx):
        """Connects rooms and amenities on a floor to the lobbies on the same floor."""
        query = """
        MATCH (lobby:Lobby), (loc:Location)
        WHERE lobby.level = loc.level AND NOT loc:Lobby
        MERGE (loc)-[:ACCESSIBLE_FROM]->(lobby)
        """
        tx.run(query)

    @staticmethod
    def _get_all_location_nodes(tx):
        """Fetches all location nodes to be used for proximity calculations."""
        result = tx.run("MATCH (n:Location) WHERE n.grid IS NOT NULL RETURN n.id AS id, n.grid AS grid")
        return [record for record in result]

    def _create_near_relationships(self, nodes):
        """
        Calculates distances between nodes and creates :NEAR relationships.
        """
        with self.driver.session(database="neo4j") as session:
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    node1 = nodes[i]
                    node2 = nodes[j]
                    dist = self._calculate_grid_distance(node1["grid"], node2["grid"])
                    if dist is not None and dist < 5: # Threshold of 5 grid units
                        session.execute_write(self._create_single_near_relationship, node1["id"], node2["id"], dist)

    @staticmethod
    def _create_single_near_relationship(tx, id1, id2, distance):
        query = """
        MATCH (a:Location {id: $id1})
        MATCH (b:Location {id: $id2})
        MERGE (a)-[r:NEAR]->(b)
        SET r.distance = $distance
        """
        tx.run(query, id1=id1, id2=id2, distance=distance)

    def _calculate_grid_distance(self, grid1, grid2):
        """
        A simple function to estimate distance based on the grid coordinates.
        """
        try:
            match1 = re.match(r"([A-Z]+)(\d+)", grid1)
            match2 = re.match(r"([A-Z]+)(\d+)", grid2)
            if not match1 or not match2: return None
            char_code1 = ord(match1.group(1).upper()) - ord('A')
            char_code2 = ord(match2.group(1).upper()) - ord('A')
            num1 = int(match1.group(2))
            num2 = int(match2.group(2))
            return math.sqrt((char_code1 - char_code2)**2 + (num1 - num2)**2)
        except (TypeError, ValueError):
            return None

    # --- STEP 4: QUERY THE GRAPH ---
    def query_graph(self):
        """Runs a series of example queries and prints the results."""
        with self.driver.session(database="neo4j") as session:
            print("\n--- Running Example Queries ---")

            # Query 1: Find a specific room
            room_name = "Death Star"
            result = session.execute_read(self._find_location, room_name)
            print(f"\n1. Where is '{room_name}'?")
            if result:
                print(f"   -> Found at Level {result['level']}, Grid {result['grid']}.")
            else:
                print(f"   -> Room '{room_name}' not found.")

            # Query 2: Find rooms near another location
            start_location_name = "Delta Vega"
            results = session.execute_read(self._find_nearby_locations, start_location_name)
            print(f"\n2. What's near '{start_location_name}'?")
            if results:
                for record in results:
                    print(f"   -> {record['name']} (Type: {record['type']}, Distance: {record['distance']:.2f})")
            else:
                print(f"   -> Nothing found near '{start_location_name}'.")

    @staticmethod
    def _find_location(tx, name):
        query = """
        MATCH (loc:Location {name: $name})
        RETURN loc.grid AS grid, loc.level AS level
        """
        result = tx.run(query, name=name)
        return result.single()

    @staticmethod
    def _find_nearby_locations(tx, name):
        query = """
        MATCH (start_loc:Location {name: $name})-[r:NEAR]-(nearby_loc:Location)
        RETURN
            nearby_loc.name AS name,
            r.distance as distance,
            // This gets the specific label like 'ConferenceRoom' or 'Lobby'
            [l IN labels(nearby_loc) WHERE l <> 'Location'][0] AS type
        ORDER BY r.distance
        LIMIT 10
        """
        result = tx.run(query, name=name)
        return [record for record in result]

if __name__ == "__main__":
    # Ensure you have the neo4j Python driver installed:
    # pip install neo4j
    # Also, ensure your Neo4j database has the APOC plugin installed.

    json_file_path = 'en-map3.json'
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        print(f"Successfully loaded data from {json_file_path}")
    except FileNotFoundError:
        print(f"ERROR: The file '{json_file_path}' was not found.")
        exit()
    except json.JSONDecodeError:
        print(f"ERROR: The file '{json_file_path}' contains invalid JSON.")
        exit()

    graph = EndeavorGraph(URI, AUTH[0], AUTH[1])
    graph.load_nodes_from_json(data)
    graph.create_relationships()
    graph.query_graph()
    graph.close()

