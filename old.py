import json
import re
from neo4j import GraphDatabase

# --- STEP 1: NEO4J DATABASE CONFIGURATION ---
# Replace with your Neo4j database credentials.
# You can often find this information in the Neo4j Desktop application
# or your cloud provider's dashboard.
URI = "neo4j://0.0.0.0:7687"  # Example: "neo4j+s://<unique_id>.databases.neo4j.io"
AUTH = ("neo4j", "your_password") # Default user is 'neo4j'

# --- JSON DATA ---
# For this script, we'll embed the JSON data directly.
# In a larger application, you would load this from a file:
# with open('endeavor_map.json', 'r') as f:
#     DATA = json.load(f)
JSON_DATA = """
[
  { "id": "L1-Lobby1", "type": "Lobby", "name": "Lobby near Shuttle Stop", "level": 1, "location": { "grid": "D8" }, "attributes": {} },
  { "id": "L1-Lobby2", "type": "Lobby", "name": "Lobby near Walsh Ave", "level": 1, "location": { "grid": "J8" }, "attributes": {} },
  { "id": "L1-Cafeteria", "type": "Amenity", "name": "Cafeteria", "level": 1, "location": { "grid": "G3" }, "attributes": {} },
  { "id": "L1-Restrooms", "type": "Amenity", "name": "Restrooms", "level": 1, "location": { "grid": "E2" }, "attributes": {} },
  { "id": "L3-PantryBar", "type": "Amenity", "name": "Shannon's Pantry/Bar", "level": 3, "location": { "grid": "Q28" }, "attributes": {} },
  { "id": "L1-1065", "type": "ConferenceRoom", "name": "Alien", "level": 1, "location": { "grid": "F8" }, "attributes": { "space_number": "L1-1065" }},
  { "id": "L1-5065", "type": "ConferenceRoom", "name": "Alpha Quadrant", "level": 1, "location": { "grid": "L3" }, "attributes": { "space_number": "L1-5065" }},
  { "id": "L1-2130", "type": "ConferenceRoom", "name": "Andoria (Restricted)", "level": 1, "location": { "grid": "F10" }, "attributes": { "space_number": "L1-2130" }},
  { "id": "L1-3060", "type": "ConferenceRoom", "name": "Badlands", "level": 1, "location": { "grid": "C3" }, "attributes": { "space_number": "L1-3060" }},
  { "id": "L1-1114", "type": "ConferenceRoom", "name": "Bajoran", "level": 1, "location": { "grid": "E9" }, "attributes": { "space_number": "L1-1114" }},
  { "id": "L1-5045", "type": "ConferenceRoom", "name": "Bermuda Triangle", "level": 1, "location": { "grid": "K2" }, "attributes": { "space_number": "L1-5045" }},
  { "id": "L1-3065", "type": "ConferenceRoom", "name": "Bird Of Prey", "level": 1, "location": { "grid": "B3" }, "attributes": { "space_number": "L1-3065" }},
  { "id": "L1-1115", "type": "ConferenceRoom", "name": "Borg", "level": 1, "location": { "grid": "E9" }, "attributes": { "space_number": "L1-1115" }},
  { "id": "L1-1124", "type": "ConferenceRoom", "name": "Box", "level": 1, "location": { "grid": "E8" }, "attributes": { "space_number": "L1-1124" }},
  { "id": "L1-3050", "type": "ConferenceRoom", "name": "Briar Patch", "level": 1, "location": { "grid": "B3" }, "attributes": { "space_number": "L1-3050" }},
  { "id": "L1-1215", "type": "ConferenceRoom", "name": "Celti Alpha", "level": 1, "location": { "grid": "E4" }, "attributes": { "space_number": "L1-1215" }},
  { "id": "L1-1134", "type": "ConferenceRoom", "name": "City of Domes", "level": 1, "location": { "grid": "D6" }, "attributes": { "space_number": "L1-1134" }},
  { "id": "L1-1230", "type": "ConferenceRoom", "name": "Cloud City", "level": 1, "location": { "grid": "F4" }, "attributes": { "space_number": "L1-1230" }},
  { "id": "L1-1135", "type": "ConferenceRoom", "name": "Colonial Viper", "level": 1, "location": { "grid": "D6" }, "attributes": { "space_number": "L1-1135" }},
  { "id": "L1-1144", "type": "ConferenceRoom", "name": "Cylon", "level": 1, "location": { "grid": "C5" }, "attributes": { "space_number": "L1-1144" }},
  { "id": "L1-1145", "type": "ConferenceRoom", "name": "Data", "level": 1, "location": { "grid": "C5" }, "attributes": { "space_number": "L1-1145" }},
  { "id": "L1-0330", "type": "ConferenceRoom", "name": "Death Star", "level": 1, "location": { "grid": "F6" }, "attributes": { "space_number": "L1-0330" }},
  { "id": "L2-0130", "type": "ConferenceRoom", "name": "Altair IV", "level": 2, "location": { "grid": "T17" }, "attributes": { "space_number": "L2-0130" }},
  { "id": "L2-0125", "type": "ConferenceRoom", "name": "Arcturus", "level": 2, "location": { "grid": "U18" }, "attributes": { "space_number": "L2-0125" }},
  { "id": "M-0205", "type": "ConferenceRoom", "name": "District 9", "level": 3, "location": { "grid": "R31" }, "attributes": { "space_number": "M-0205" }},
  { "id": "M-0210", "type": "ConferenceRoom", "name": "Hogsmeade", "level": 3, "location": { "grid": "S30" }, "attributes": { "space_number": "M-0210" }}
]
"""

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
        It uses MERGE to avoid creating duplicate nodes on subsequent runs.
        """
        with self.driver.session(database="neo4j") as session:
            # Clear the database before loading to ensure a fresh start
            session.execute_write(self._clear_database)
            print("Cleared existing database.")

            # This is the Cypher query to create nodes.
            # It iterates through the list of locations passed as a parameter.
            result = session.execute_write(self._create_nodes, data)
            print(f"Successfully created {result['nodes_created']} nodes and {result['labels_set']} labels.")

    @staticmethod
    def _clear_database(tx):
        """Deletes all nodes and relationships."""
        tx.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _create_nodes(tx, locations):
        """
        Creates a node for each location in the provided data.
        It also dynamically sets a label based on the 'type' field.
        """
        query = """
        UNWIND $locations AS loc
        // Create the node with its properties
        MERGE (n:Location {id: loc.id})
        SET n.name = loc.name,
            n.level = loc.level,
            n.grid = loc.location.grid
        // Dynamically add the specific label (e.g., :ConferenceRoom, :Lobby)
        WITH n, 'MERGE (m:Location {id: \"' + n.id + '\"}) SET m:' + loc.type AS aquery
        CALL apoc.cypher.doIt(aquery, {}) YIELD value
        RETURN count(n) AS nodes_created, count(value) as labels_set
        """
        result = tx.run(query, locations=locations)
        return result.single()

    # --- STEP 3: CREATE RELATIONSHIPS ---
    def create_relationships(self):
        """
        Creates meaningful relationships between the nodes to build the graph.
        """
        with self.driver.session(database="neo4j") as session:
            # Create :LOCATED_ON relationships
            session.execute_write(self._create_located_on_relationships)
            print("Created :LOCATED_ON relationships.")

            # Create :ACCESSIBLE_FROM relationships to Lobbies
            session.execute_write(self._create_accessible_from_relationships)
            print("Created :ACCESSIBLE_FROM relationships.")

            # Create :NEAR relationships based on grid proximity
            # We need to fetch all nodes to do this calculation in Python
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
        This part is done in Python to handle the grid logic.
        """
        with self.driver.session(database="neo4j") as session:
            # This is a brute-force comparison of every node with every other node.
            # For a very large dataset, this could be optimized.
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    node1 = nodes[i]
                    node2 = nodes[j]

                    dist = self._calculate_grid_distance(node1["grid"], node2["grid"])

                    # If the calculated distance is less than a threshold, create a relationship
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
        Example: 'F8' -> ('F', 8)
        """
        try:
            # Use regex to split letters and numbers
            match1 = re.match(r"([A-Z]+)(\d+)", grid1)
            match2 = re.match(r"([A-Z]+)(\d+)", grid2)

            if not match1 or not match2:
                return None

            # Letter part (A=1, B=2, etc.)
            char_code1 = ord(match1.group(1).upper()) - ord('A')
            char_code2 = ord(match2.group(1).upper()) - ord('A')

            # Number part
            num1 = int(match1.group(2))
            num2 = int(match2.group(2))

            # Calculate Euclidean distance
            distance = ((char_code1 - char_code2)**2 + (num1 - num2)**2)**0.5
            return distance
        except (TypeError, ValueError):
            # Handle cases where grid is null or malformed
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
                print("   -> Room not found.")

            # Query 2: Find rooms near a lobby
            lobby_name = "Lobby near Walsh Ave"
            results = session.execute_read(self._find_nearby_locations, lobby_name)
            print(f"\n2. What's near the '{lobby_name}'?")
            if results:
                for record in results:
                    print(f"   -> {record['name']} (Type: {record['type']}, Distance: {record['distance']:.2f})")
            else:
                print("   -> Nothing found nearby.")

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
        // Get the specific label of the nearby location
        CALL apoc.meta.cypher.read("MATCH (n:Location {id: $id}) RETURN labels(n) as labels", {id: nearby_loc.id}) YIELD value
        RETURN nearby_loc.name AS name, r.distance as distance, [l in value.labels WHERE l <> 'Location'][0] as type
        ORDER BY r.distance
        LIMIT 10
        """
        result = tx.run(query, name=name)
        return [record for record in result]


if __name__ == "__main__":
    # Ensure you have the neo4j Python driver installed:
    # pip install neo4j

    # Also, ensure your Neo4j database has the APOC plugin installed.
    # It comes standard with Neo4j Desktop.

    # Initialize the graph manager with your database credentials
    graph = EndeavorGraph(URI, AUTH[0], AUTH[1])

    # Load the JSON data into nodes
    data = json.loads(JSON_DATA)
    graph.load_nodes_from_json(data)

    # Create relationships
    graph.create_relationships()

    # Run example queries
    graph.query_graph()

    # Clean up and close the connection
    graph.close()



