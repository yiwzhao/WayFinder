import re
from neo4j import GraphDatabase
from openai import OpenAI
import math
import os
from fastmcp import FastMCP

class EndeavorRAG:
    def __init__(self, uri, user, password, openai_api_key, base_url=None):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.llm = OpenAI(
            api_key=openai_api_key,
            base_url=base_url if base_url else "https://api.openai.com/v1"  # fallback to OpenAI if not NVIDIA
        )

    def close(self):
        self.driver.close()

    def parse_user_query_with_openai(self, text):
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

    def parse_user_query(self, text):
        prompt = f"""
            You are a helpful assistant that extracts locations from natural language navigation queries.

            Extract the start and end locations from the following sentence:
            "{text}"

            Return a JSON object like this: {{"start": "Room A", "end": "Room B"}}
        """
        response = self.llm.chat.completions.create(
            model="qwen/qwen3-235b-a22b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
            stream=True,
            extra_body={"chat_template_kwargs": {"thinking": True}}
        )

        output = ""
        for chunk in response:
            content = getattr(chunk.choices[0].delta, "content", "")
            if content:
                output += content

        match = re.search(r'\{.*?\}', output, re.DOTALL)
        if match:
            locs = eval(match.group())
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
                MATCH path = shortestPath((start)-[:NEAR|CONNECTS_TO*]-(end))
                RETURN [node IN nodes(path) | node.name] AS names
            """, start=start_name, end=end_name)
            record = result.single()
            return record["names"] if record else []

    def render_path_to_instruction0(self, path):
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

    def render_path_to_instruction1(self, path_names):
        node_infos = self.get_node_details(path_names)
        if not node_infos:
            return "No valid path found or coordinates missing."
        return self.generate_directions(node_infos)

    def render_path_to_instruction_with_openai(self, path):
        if not path:
            return "Sorry, I couldn't find a valid path."
        if len(path) == 1:
            return f"You are already at {path[0]}."

        node_infos = self.get_node_details(path)
        if not node_infos:
            return "No valid path found or coordinates missing."
        #return self.generate_directions(node_infos)
        prompt = f"""
            You are a navigation assistant. Convert the following ordered list of locations into step-by-step natural English walking directions:

            Path: {self.generate_directions(node_infos)}
            """
        response = self.llm.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    def render_path_to_instruction(self, path):
        if not path:
            return "Sorry, I couldn't find a valid path."
        if len(path) == 1:
            return f"You are already at {path[0]}."

        node_infos = self.get_node_details(path)
        if not node_infos:
            return "No valid path found or coordinates missing."

        path_description = self.generate_directions(node_infos)

        prompt = f"""
            You are a navigation assistant. Convert the following ordered list of locations into step-by-step natural English walking directions:

            Path: {path_description}
        """

        response = self.llm.chat.completions.create(
            model="qwen/qwen3-235b-a22b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
            stream=True,
            extra_body={"chat_template_kwargs": {"thinking": True}}
        )

        output = ""
        for chunk in response:
            content = getattr(chunk.choices[0].delta, "content", "")
            if content:
                output += content

        return output.strip()
    
    def get_node_details(self, path_names):
        with self.driver.session(database="neo4j") as session:
            result = session.run("""
                UNWIND $names AS name
                MATCH (n:Location {name: name})
                RETURN n.name AS name, n.grid AS grid, n.level AS level
            """, names=path_names)
            return [record.data() for record in result]
    
    def parse_grid(self, grid):
        match = re.match(r"([A-Z]+)(\d+)", grid)
        if not match:
            return None
        col = sum((ord(c) - ord('A') + 1) * (26 ** i) for i, c in enumerate(reversed(match.group(1))))
        row = int(match.group(2))
        return (col, row)

    def generate_directions(self, node_infos):
        if len(node_infos) < 2:
            return "You are already at the destination."

        steps = []
        for i in range(len(node_infos) - 1):
            cur, nxt = node_infos[i], node_infos[i+1]
            pos1 = self.parse_grid(cur['grid'])
            pos2 = self.parse_grid(nxt['grid'])
            if not pos1 or not pos2:
                continue
            dx, dy = pos2[0] - pos1[0], pos2[1] - pos1[1]
            direction = self._vector_to_direction(dx, dy)
            distance = round((dx ** 2 + dy ** 2) ** 0.5 * 1.5, 1)  # 假设每单位 = 1.5米
            step = f"From '{cur['name']}', go {direction} for {distance} meters to '{nxt['name']}'"
            if cur['level'] != nxt['level']:
                step += f" (and go to Level {nxt['level']})"
            steps.append(step)
        return "\n".join(steps)

    def _vector_to_direction(self, dx, dy):
        angle = math.degrees(math.atan2(dy, dx)) % 360
        dirs = [
            (0, "south"), (45, "southeast"), (90, "east"),
            (135, "northeast"), (180, "north"),
            (225, "northwest"), (270, "west"), (315, "southwest")
        ]
        closest = min(dirs, key=lambda d: abs(d[0] - angle))
        return closest[1]




mcp = FastMCP("EndeavorRAG 🚀")
@mcp.tool
def endeavor_rag_directory(user_input: str) -> str:
    """
    Use this tool to get directions from one location to another in the Endeavor building.
    """
    URI = "neo4j://localhost:7687"
    AUTH = ("neo4j", "graphrag")
    #OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_KEY = os.getenv("NV_API_KEY")

    #rag = EndeavorRAG(URI, AUTH[0], AUTH[1], OPENAI_API_KEY)
    rag = EndeavorRAG(
        URI, AUTH[0], AUTH[1],
        OPENAI_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1"
    )

    #user_input = "How do I get from Force Field to Cafeteria?"
    #user_input = "How do I get from Jabba's Palace to Cafeteria?"
    #user_input = "How do I get from Cafeteria to WestWorld?"
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
    return instructions

if __name__ == "__main__":
    print("Starting EndeavorRAG MCP server...")
    mcp.run(transport="http", host="0.0.0.0", port=8008, path="/mcp")
    