import json
import re
from neo4j import GraphDatabase
import math

# --- STEP 1: NEO4J DATABASE CONFIGURATION ---
# Replace with your Neo4j database credentials.
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "graphrag") # Using the password from your previous script

# --- DATA LOADING ---
# This script loads data from 'en-map.json'.

class EndeavorGraph:
    """
    A class to manage the creation and querying of the Endeavor building graph.
    """
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Successfully connected to Neo4j database.")

    def close(self):
        self.driver.close()
        print("Database connection closed.")

    # --- STEP 2: LOAD NODES INTO THE DATABASE ---
    def load_nodes_from_json(self, data):
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._clear_database)
            print("Cleared existing database.")
            result = session.execute_write(self._create_nodes, data)
            #print(f"Successfully created nodes and set {result['labels_set']} labels.")

    @staticmethod
    def _clear_database(tx):
        """Deletes all nodes and relationships."""
        tx.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _create_nodes(tx, locations):
        query = """
        UNWIND $locations AS loc
        WITH loc,
             toLower(split(loc.type, " ")[0]) AS base_label,
             coalesce(loc.location.grid, null) AS grid,
             coalesce(loc.attributes.space_number, null) AS space_number

        MERGE (n:Location {id: loc.id})
        SET n.name = loc.name,
            n.level = loc.level,
            n.grid = grid,
            n.space_number = space_number,
            n.direction_hint = coalesce(loc.attributes.direction_hint, null),
            n.floor_accessible = coalesce(loc.attributes.floor_accessible, null)

        WITH n, base_label
        CALL apoc.create.addLabels(n, [toUpper(substring(base_label,0,1)) + substring(base_label,1)]) YIELD node
        RETURN count(*) AS nodes_created
        """
        result = tx.run(query, locations=locations)
        return result.single()
        query = """
        UNWIND $locations AS loc
        WITH loc,
             replace(loc.type, " ", "_") AS label,
             coalesce(loc.location.grid, null) AS grid,
             coalesce(loc.attributes.space_number, null) AS space_number

        MERGE (n:Location {id: loc.id})
        SET n.name = loc.name,
            n.level = loc.level,
            n.grid = grid,
            n.space_number = space_number

        WITH n, label
        CALL apoc.create.addLabels(n, [label]) YIELD node
        RETURN count(*) AS nodes_created
        """
        result = tx.run(query, locations=locations)
        return result.single()

    # --- STEP 3: CREATE RELATIONSHIPS ---
    def create_relationships(self):
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._create_located_on_relationships)
            print("Created :LOCATED_ON relationships.")
            session.execute_write(self._create_accessible_from_relationships)
            print("Created :ACCESSIBLE_FROM relationships.")
            session.execute_write(self._create_stair_connections)
            print("Created :CONNECTS_TO relationships for stairs.")
            nodes = session.execute_read(self._get_all_location_nodes)
            self._create_near_relationships(nodes)
            print("Created :NEAR relationships.")

    @staticmethod
    def _create_located_on_relationships(tx):
        tx.run("""
        MATCH (loc:Location) WHERE loc.level IS NOT NULL
        MERGE (lvl:Level {number: loc.level})
        MERGE (loc)-[:LOCATED_ON]->(lvl)
        """)

    @staticmethod
    def _create_accessible_from_relationships(tx):
        tx.run("""
        MATCH (lobby:Lobby), (loc:Location)
        WHERE lobby.level = loc.level AND NOT loc:Lobby
        MERGE (loc)-[:ACCESSIBLE_FROM]->(lobby)
        """)

    @staticmethod
    def _create_stair_connections(tx):
        """Creates CONNECTS_TO relationships between stairs on different floors."""
        stair_connections = [
            {'from': 'L1-Stair-C7', 'to': 'L2-Stair-R18'},
            {'from': 'L1-Stair-E7', 'to': 'L2-Stair-T18'},
            {'from': 'L1-Stair-I7', 'to': 'L2-Stair-V18'},
            {'from': 'L1-Stair-K7', 'to': 'L2-Stair-X18'}
        ]
        query = """
        UNWIND $connections AS conn
        MATCH (a:Stair {id: conn.from})
        MATCH (b:Stair {id: conn.to})
        // Create bidirectional connection for pathfinding
        MERGE (a)-[:CONNECTS_TO {type: 'vertical'}]->(b)
        MERGE (b)-[:CONNECTS_TO {type: 'vertical'}]->(a)
        """
        tx.run(query, connections=stair_connections)

    @staticmethod
    def _get_all_location_nodes(tx):
        result = tx.run("MATCH (n:Location) WHERE n.grid IS NOT NULL RETURN n.id AS id, n.grid AS grid")
        return [record for record in result]

    def _create_near_relationships(self, nodes):
        with self.driver.session(database="neo4j") as session:
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    node1, node2 = nodes[i], nodes[j]
                    dist = self._calculate_grid_distance(node1["grid"], node2["grid"])
                    if dist is not None and dist < 5:
                        session.execute_write(self._create_single_near_relationship, node1["id"], node2["id"], dist)

    @staticmethod
    def _create_single_near_relationship(tx, id1, id2, distance):
        tx.run("""
        MATCH (a:Location {id: $id1})
        MATCH (b:Location {id: $id2})
        MERGE (a)-[r:NEAR {distance: $distance}]->(b)
        MERGE (b)-[r2:NEAR {distance: $distance}]->(a)
        """, id1=id1, id2=id2, distance=round(distance, 2))

    def _calculate_grid_distance(self, grid1, grid2):
        try:
            match1 = re.match(r"([A-Z]+)(\d+)", grid1)
            match2 = re.match(r"([A-Z]+)(\d+)", grid2)
            if not match1 or not match2: return None
            char_code1, num1 = ord(match1.group(1).upper()) - ord('A'), int(match1.group(2))
            char_code2, num2 = ord(match2.group(1).upper()) - ord('A'), int(match2.group(2))
            return math.sqrt((char_code1 - char_code2)**2 + (num1 - num2)**2)
        except (TypeError, ValueError):
            return None

    # --- STEP 4: QUERY THE GRAPH ---
    def query_graph(self):
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

            # Query 2: Find nearby locations
            start_location_name = "Delta Vega"
            results = session.execute_read(self._find_nearby_locations, start_location_name)
            print(f"\n2. What's near '{start_location_name}'?")
            if results:
                for record in results:
                    print(f"   -> {record['name']} (Type: {record['type']}, Distance: {record['distance']:.2f})")
            else:
                print(f"   -> Nothing found near '{start_location_name}'.")

            # --- NEW: Query 3 - Pathfinding from Level 2 to Level 1 ---
            path_results = session.execute_read(self._find_path_between_locations, "Altair IV", "Cafeteria")
            print(f"\n3. What is the shortest path from 'Altair IV' to the 'Cafeteria'?")
            if path_results:
                path_description = " -> ".join([res['name'] for res in path_results])
                print(f"   -> Path: {path_description}")
            else:
                print("   -> No path found.")

    @staticmethod
    def _find_location(tx, name):
        result = tx.run("MATCH (loc:Location {name: $name}) RETURN loc.grid AS grid, loc.level AS level", name=name)
        return result.single()

    @staticmethod
    def _find_nearby_locations(tx, name):
        result = tx.run("""
        MATCH (start:Location {name: $name})-[r:NEAR]-(nearby:Location)
        RETURN nearby.name AS name, r.distance as distance, [l IN labels(nearby) WHERE l <> 'Location'][0] AS type
        ORDER BY r.distance LIMIT 10
        """, name=name)
        return [record for record in result]

    @staticmethod
    def _find_path_between_locations(tx, start_name, end_name):
        """Finds the shortest path between two locations, even across floors."""
        query = """
        MATCH (start:Location {name: $start_name}), (end:Location {name: $end_name})
        // Find the shortest path using a combination of NEAR and CONNECTS_TO relationships
        CALL gds.graph.project.cypher(
          'myGraph',
          'MATCH (n:Location) RETURN id(n) AS id',
          'MATCH (n1:Location)-[r:NEAR|CONNECTS_TO]-(n2:Location) RETURN id(n1) AS source, id(n2) AS target'
        )
        YIELD graphName
        CALL gds.shortestPath.dijkstra.stream('myGraph', {
          sourceNode: id(start),
          targetNode: id(end)
        })
        YIELD path
        RETURN [node IN nodes(path) | node.name] AS names
        """
        # This advanced query requires the Graph Data Science (GDS) library in Neo4j
        # A simpler, but potentially slower, alternative is below:
        simple_query = """
        MATCH (start:Location {name: $start_name}), (end:Location {name: $end_name})
        MATCH p = shortestPath((start)-[:NEAR|CONNECTS_TO*..50]-(end))
        RETURN [node IN nodes(p) | node.name] AS names
        """
        result = tx.run(simple_query, start_name=start_name, end_name=end_name)
        record = result.single()
        # The result is a list of names, so we just need to re-format it for the printout
        return [{'name': name} for name in record['names']] if record else None

if __name__ == "__main__":
    json_file_path = 'en-map4.json'
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


