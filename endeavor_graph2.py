import json
import re
from neo4j import GraphDatabase

class EndeavorGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Connected to Neo4j.")

    def close(self):
        self.driver.close()

    def load_nodes_from_json(self, data):
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._clear_database)
            print("Cleared DB.")
            result = session.execute_write(self._create_nodes, data)
            print(f"Created {result['nodes_created']} nodes.")

    @staticmethod
    def _clear_database(tx):
        tx.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _create_nodes(tx, locations):
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

    def create_relationships(self):
        with self.driver.session(database="neo4j") as session:
            session.execute_write(self._create_located_on_relationships)
            print("Created :LOCATED_ON.")

            session.execute_write(self._create_accessible_from_relationships)
            print("Created :ACCESSIBLE_FROM.")

            session.execute_write(self._create_stairs_to_relationships)
            print("Created :STAIRS_TO.")

            nodes = session.execute_read(self._get_all_location_nodes)
            self._create_near_relationships(nodes)
            print("Created :NEAR.")

    @staticmethod
    def _create_located_on_relationships(tx):
        query = """
        MATCH (loc:Location)
        WHERE loc.level IS NOT NULL
        MERGE (lvl:Level {number: loc.level})
        MERGE (loc)-[:LOCATED_ON]->(lvl)
        """
        tx.run(query)

    @staticmethod
    def _create_accessible_from_relationships(tx):
        query = """
        MATCH (lobby:Lobby), (loc:Location)
        WHERE lobby.level = loc.level AND NOT loc:Lobby
        MERGE (loc)-[:ACCESSIBLE_FROM]->(lobby)
        """
        tx.run(query)

    @staticmethod
    def _create_stairs_to_relationships(tx):
        query = """
        MATCH (a:Stairs), (b:Stairs)
        WHERE a.grid = b.grid AND a.level <> b.level
        MERGE (a)-[:STAIRS_TO]->(b)
        """
        tx.run(query)

    @staticmethod
    def _get_all_location_nodes(tx):
        result = tx.run("MATCH (n:Location) WHERE n.grid IS NOT NULL RETURN n.id AS id, n.grid AS grid, n.level AS level")
        return [record for record in result]

    def _create_near_relationships(self, nodes):
        with self.driver.session(database="neo4j") as session:
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    node1 = nodes[i]
                    node2 = nodes[j]
                    if node1["level"] != node2["level"]:
                        continue
                    dist = self._calculate_grid_distance(node1["grid"], node2["grid"])
                    if dist is not None and dist <= 3:
                        session.execute_write(self._create_single_near_relationship, node1["id"], node2["id"], dist)
                        session.execute_write(self._create_single_near_relationship, node2["id"], node1["id"], dist)

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
        try:
            match1 = re.match(r"([A-Z]+)(\d+)", grid1)
            match2 = re.match(r"([A-Z]+)(\d+)", grid2)
            if not match1 or not match2:
                return None
            x1 = self._col_to_num(match1.group(1))
            x2 = self._col_to_num(match2.group(1))
            y1 = int(match1.group(2))
            y2 = int(match2.group(2))
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        except:
            return None


    def _col_to_num(self, letters):
        result = 0
        for c in letters:
            result = result * 26 + (ord(c.upper()) - ord('A') + 1)
        return result

if __name__ == "__main__":
    URI = "neo4j://localhost:7687"
    AUTH = ("neo4j", "graphrag")
    json_path = "en-map3.json"

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print("Error loading JSON:", e)
        exit()

    graph = EndeavorGraph(URI, AUTH[0], AUTH[1])
    graph.load_nodes_from_json(data)
    graph.create_relationships()
    graph.close()