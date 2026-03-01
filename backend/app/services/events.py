from datetime import datetime, timedelta
import random

def seed_events_near_unl(now: datetime):
    base = [
        ("Basketball Watch Party", "Student Union", 40.8202, -96.7009),
        ("Career Fair Mixer", "Howard L. Hawks Hall", 40.8194, -96.7026),
        ("Club Meeting Night", "Avery Hall", 40.8199, -96.7038),
        ("Guest Lecture", "Love Library", 40.8197, -96.7020),
        ("Study Jam", "Kauffman Center", 40.8187, -96.7008),
    ]

    events = []
    for title, loc, lat, lon in base:
        start = now + timedelta(hours=random.choice([1, 2, 3, 5, 8, 12]))
        end = start + timedelta(hours=random.choice([1, 2]))
        events.append({
            "title": title,
            "location_name": loc,
            "lat": lat + random.uniform(-0.0005, 0.0005),
            "lon": lon + random.uniform(-0.0005, 0.0005),
            "start_time": start,
            "end_time": end,
        })
    return events

def time_bump_intensity(now: datetime):
    hour = now.hour
    minute = now.minute

    base = 0.25

    # lunch movement
    if 11 <= hour <= 13:
        base += 0.25

    # class passing periods-ish
    if minute >= 45 or minute <= 10:
        base += 0.25

    # evening activity
    if 18 <= hour <= 21:
        base += 0.15

    return min(1.0, base)