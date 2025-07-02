import json, psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime

PG_DSN = "dbname=meeting_rooms user=postgres password=postgres host=localhost port=5432"

def load_rooms(conn, rooms):
    sql = """INSERT INTO rooms(room_id,name,level,grid,capacity,type)
             VALUES (%(id)s,%(name)s,%(level)s,%(grid)s,%(capacity)s,%(type)s)
             ON CONFLICT (room_id) DO NOTHING;"""
    payload = [
        {
            "id": r["id"],
            "name": r["name"],
            "level": r.get("level"),
            "grid": r["location"]["grid"],
            "capacity": r.get("capacity", None),
            "type": r["type"].replace(" ", "")
        }
        for r in rooms
    ]
    execute_batch(conn.cursor(), sql, payload)

def load_bookings(conn, bookings):
    sql = """INSERT INTO bookings(room_id,timeslot,booked_by,title)
             VALUES (%s, tsrange(%s, %s, '[)') , %s, %s);"""
    payload = [
        (
            b["room_id"],
            b["start"],
            b["end"],
            b["booked_by"],
            b.get("title","")
        )
        for b in bookings
    ]
    execute_batch(conn.cursor(), sql, payload)

def main():

    
    with open("en-map.json") as f:
        rooms = json.load(f)
    with open("bookings.json") as f:
        bookings = json.load(f)

    with psycopg2.connect(PG_DSN) as conn:
        conn.autocommit = False
        load_rooms(conn, rooms)
        load_bookings(conn, bookings)
        conn.commit()
        print("✅ Data imported.")

if __name__ == "__main__":
    main()
