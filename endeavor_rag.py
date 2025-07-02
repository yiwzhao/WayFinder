import re
from neo4j import GraphDatabase
from openai import OpenAI
import os

class EndeavorRAG:
    def __init__(self, uri, user, password, openai_api_key):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.llm = OpenAI(api_key=openai_api_key)

    def close(self):
        self.driver.close()

    def parse_user_query(self, text):
        """
        Use LLM to extract start and end locations from a natural language query.
        """
        prompt = f"""
            You are a helpful assistant that extracts locations from natural language navigation queries.

            Extract the start and end locations from the following sentence:
            "{text}"

            Return a JSON object like this: {{"start": "Room A", "end": "Room B"}}
            """
        response = self.llm.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content
        match = re.search(r'\{.*?\}', reply, re.DOTALL)
        if match:
            locs = eval(match.group())  # Simple JSON-like extraction
            return locs['start'], locs['end']
        raise ValueError("Could not parse locations from LLM response")

    def get_shortest_path_gds(self, start_name, end_name):
        #hold on, I need to check if the start and end are valid locations
        with self.driver.session(database="neo4j") as session:
            result = session.run("""
                MATCH (start:Location {name: $start}), (end:Location {name: $end})
                CALL gds.shortestPath.dijkstra.stream({
                    sourceNode: start,
                    targetNode: end,
                    relationshipWeightProperty: 'distance',
                    relationshipTypes: ['NEAR', 'STAIRS_TO']
                })
                YIELD path
                RETURN [node in nodes(path) | node.name] AS names
            """, start=start_name, end=end_name)
            record = result.single()
            return record["names"] if record else []
    
    def get_shortest_path(self, start_name, end_name):
        with self.driver.session(database="neo4j") as session:
            result = session.run("""
                MATCH (start:Location {name: $start}), (end:Location {name: $end})
                MATCH path = shortestPath((start)-[:NEAR|STAIRS_TO*]-(end))
                RETURN [node IN nodes(path) | node.name] AS names
            """, start=start_name, end=end_name)
            record = result.single()
            return record["names"] if record else []

    def render_path_to_instruction(self, path):
        if not path:
            return "Sorry, I couldn't find a valid path."
        if len(path) == 1:
            return f"You are already at {path[0]}."

        prompt = f"""
            You are a navigation assistant. Convert the following ordered list of locations into step-by-step natural English walking directions:

            Path: {path}
            """
        response = self.llm.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

if __name__ == "__main__":
    URI = "neo4j://localhost:7687"
    AUTH = ("neo4j", "graphrag")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    rag = EndeavorRAG(URI, AUTH[0], AUTH[1], OPENAI_API_KEY)

    user_input = "How do I get from Force Field to Cafeteria?"
    try:
        start, end = rag.parse_user_query(user_input)
        path = rag.get_shortest_path(start, end)
        instructions = rag.render_path_to_instruction(path)
        print("Path found:", path)
        print("Instructions:", instructions)
    except Exception as e:
        print("Error:", e)
    finally:
        rag.close()