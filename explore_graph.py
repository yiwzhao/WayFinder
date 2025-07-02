from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "graphrag")

class GraphExplorer:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def show_sample_rooms(self, limit=10):
        with self.driver.session() as session:
            result = session.run("""
                MATCH (r)
                WHERE r.grid IS NOT NULL AND r.name IS NOT NULL
                RETURN r.name AS name, r.grid AS grid, r.level AS level
                LIMIT $limit
            """, parameters={"limit": limit})
            print("Sample Rooms:")
            for record in result:
                print(f" - {record['name']} at {record['grid']} (Level {record['level']})")

    def show_relationships(self):
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN DISTINCT type(r) AS rel_type, COUNT(*) AS count
            """)
            print("Relationship Types:")
            for record in result:
                print(f" - {record['rel_type']} ({record['count']})")
    
    def show_labels(self):
        with self.driver.session() as session:
            result = session.run("CALL db.labels()")
            print("All labels in DB:")
            for record in result:
                print(f" - {record['label']}")

if __name__ == "__main__":
    explorer = GraphExplorer(NEO4J_URI, NEO4J_AUTH)
    explorer.show_labels()
    explorer.show_sample_rooms()
    explorer.show_relationships()
    explorer.close()
