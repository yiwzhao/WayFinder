import json
import random
from datetime import datetime, timedelta

# 读取会议室 JSON
with open("en-map.json") as f:
    rooms = json.load(f)

# 用于生成会议记录
def generate_bookings(room_id, base_date):
    slots = []
    booked = []
    current = datetime.strptime(base_date + " 09:00", "%Y-%m-%d %H:%M")
    for _ in range(random.randint(3, 5)):
        duration = random.choice([30, 60, 90])
        end = current + timedelta(minutes=duration)
        booked.append({
            "room_id": room_id,
            "start": current.strftime("%Y-%m-%d %H:%M"),
            "end": end.strftime("%Y-%m-%d %H:%M"),
            "booked_by": random.choice(["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "George", "Hannah", "Ivy", "Jack", "Kathy", "Larry", "Mia", "Nate", "Olivia", "Peter", "Quinn", "Rachel", "Sam", "Tina", "Ursula", "Victor", "Wendy", "Xavier", "Yvonne", "Zach","Zoe"]),
            "title": ""
        })
        # 加一点随机间隔
        current = end + timedelta(minutes=random.randint(15, 45))
        if current.hour >= 18:
            break
    return booked

# 生成所有会议室的 bookings
all_bookings = []
for room in rooms:
    all_bookings += generate_bookings(room["id"], base_date="2025-06-26")

# 保存为 JSON
with open("bookings.json", "w") as f:
    json.dump(all_bookings, f, indent=2)

print(f"Generated {len(all_bookings)} fake bookings.")
