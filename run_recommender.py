from datetime import datetime
from recommender import PostgresBookingManager, MeetingRoomRecommender
from endeavor_graph import EndeavorGraph

# === initialize database and graph interface ===
pg_manager = PostgresBookingManager(
    dbname="meeting_rooms",
    user="postgres",
    password="postgres",
    host="localhost",
    port=5432
)

graph = EndeavorGraph(uri="neo4j://localhost:7687", user="neo4j", password="graphrag")

recommender = MeetingRoomRecommender(graph, pg_manager)

# === input example ===
user_grids = ["G2", "H2"]
start_time = datetime.strptime("2025-06-26 13:00", "%Y-%m-%d %H:%M")
end_time = datetime.strptime("2025-06-26 14:00", "%Y-%m-%d %H:%M")

# === get results ===
results = recommender.recommend(user_grids, start_time, end_time, top_k=3)

# === print results ===
print("Top recommended meeting rooms:")
for name, grid, dist, cap, typ in results:
    print(f"- {name} (Grid: {grid}, Distance: {dist:.2f}, Capacity: {cap}, Type: {typ})")

# === close Neo4j connection ===
graph.close()
