import psycopg2
from datetime import datetime
from endeavor_graph import EndeavorGraph
from heapq import heappush, heappop


class PostgresBookingManager:
    def __init__(self, dbname, user, password, host="localhost", port=5432):
        self.conn = psycopg2.connect(
            dbname=dbname, user=user, password=password,
            host=host, port=port
        )

    def is_room_available(self, room_id, start_time: datetime, 
                         end_time: datetime):
        query = """
            SELECT COUNT(*) FROM bookings
            WHERE room_id = %s AND timeslot && tsrange(%s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (room_id, start_time, end_time))
            result = cur.fetchone()
            return result[0] == 0

    def get_available_rooms(self, start_time: datetime, end_time: datetime):
        query = """
            SELECT r.room_id, r.name, r.grid, r.capacity, r.type
            FROM rooms r
            WHERE NOT EXISTS (
                SELECT 1 FROM bookings b
                WHERE b.room_id = r.room_id
                AND b.timeslot && tsrange(%s, %s)
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (start_time, end_time))
            return cur.fetchall()


class MeetingRoomRecommender:
    def __init__(self, graph: EndeavorGraph, 
                 booking_manager: PostgresBookingManager):
        self.graph = graph
        self.booking_manager = booking_manager

    def recommend(self, user_grids: list[str], start_time: datetime, 
                  end_time: datetime, top_k=3):
        available_rooms = self.booking_manager.get_available_rooms(
            start_time, end_time
        )
        if not available_rooms:
            return []

        # Use min-heap to efficiently find top-k closest rooms
        room_heap = []
        
        for room in available_rooms:
            room_id, name, grid, capacity, type_ = room
            distances = []
            
            # Calculate distance from each user grid to this room
            for user_grid in user_grids:
                dist = self.graph._calculate_grid_distance(user_grid, grid)
                if dist is not None:
                    distances.append(dist)
            
            # If we have valid distances, calculate average and add to heap
            if distances:
                avg_dist = sum(distances) / len(distances)
                heappush(room_heap, (avg_dist, name, grid, capacity, type_))
        
        # Extract top-k rooms from heap
        recommendations = []
        for _ in range(min(top_k, len(room_heap))):
            if room_heap:
                dist, name, grid, capacity, type_ = heappop(room_heap)
                recommendations.append((name, grid, dist, capacity, type_))
        
        return recommendations
    
