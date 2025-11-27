"""
Database initialization script for GoodFoods restaurant reservation system.
Creates tables and populates with 50-100 diverse restaurant locations.
"""
import sqlite3
import random
from datetime import datetime

DB_PATH = "goodfoods.db"

# Restaurant data templates
CUISINES = [
    "Italian", "Chinese", "Mediterranean", "Indian", "Japanese", 
    "Mexican", "French", "Thai", "American", "Greek", "Korean",
    "Vietnamese", "Spanish", "Brazilian", "Lebanese", "Turkish"
]

LOCATIONS = [
    "Downtown", "Uptown", "Midtown", "Waterfront", "Financial District",
    "Arts District", "Historic Quarter", "Shopping District", "Park Area",
    "Riverside", "Harbor View", "City Center", "Suburban Plaza"
]

AMBIANCES = [
    "Romantic", "Family-friendly", "Business", "Casual", "Upscale",
    "Intimate", "Lively", "Quiet", "Trendy", "Traditional"
]

RESTAURANT_NAMES = [
    # Italian
    ("Luigi's Trattoria", "Italian"), ("Bella Vista", "Italian"), ("Nonna's Kitchen", "Italian"),
    ("Roma Ristorante", "Italian"), ("Pasta Paradiso", "Italian"), ("Casa Italiana", "Italian"),
    
    # Chinese
    ("Golden Dragon", "Chinese"), ("Jade Garden", "Chinese"), ("Peking Palace", "Chinese"),
    ("Shanghai Express", "Chinese"), ("Lucky Bamboo", "Chinese"), ("Dragon's Den", "Chinese"),
    
    # Mediterranean
    ("Aegean Breeze", "Mediterranean"), ("Olive Grove", "Mediterranean"), ("Santorini", "Mediterranean"),
    ("Coastal Med", "Mediterranean"), ("Sunset Terrace", "Mediterranean"),
    
    # Indian
    ("Taj Mahal", "Indian"), ("Spice Route", "Indian"), ("Curry House", "Indian"),
    ("Bombay Palace", "Indian"), ("Namaste", "Indian"), ("Royal India", "Indian"),
    
    # Japanese
    ("Sakura Sushi", "Japanese"), ("Tokyo Grill", "Japanese"), ("Zen Garden", "Japanese"),
    ("Hibachi Express", "Japanese"), ("Wasabi", "Japanese"), ("Sushi Master", "Japanese"),
    
    # Mexican
    ("El Mariachi", "Mexican"), ("Casa Mexico", "Mexican"), ("Fiesta Grande", "Mexican"),
    ("Taco Loco", "Mexican"), ("Cantina Real", "Mexican"),
    
    # French
    ("Le Bistro", "French"), ("Champagne Room", "French"), ("Parisian", "French"),
    ("Belle Époque", "French"), ("Café de Paris", "French"),
    
    # Thai
    ("Bangkok Garden", "Thai"), ("Siam Spice", "Thai"), ("Thai Orchid", "Thai"),
    ("Golden Temple", "Thai"),
    
    # American
    ("The Grill House", "American"), ("Burger Junction", "American"), ("Steak & Co", "American"),
    ("Rustic Kitchen", "American"), ("Diner Classic", "American"), ("BBQ Pit", "American"),
    
    # Greek
    ("Athens Taverna", "Greek"), ("Olympus", "Greek"), ("Aegean", "Greek"),
    
    # Korean
    ("Seoul Kitchen", "Korean"), ("K-BBQ", "Korean"), ("Kimchi House", "Korean"),
    
    # Vietnamese
    ("Pho Saigon", "Vietnamese"), ("Hanoi Express", "Vietnamese"),
    
    # Spanish
    ("Tapas Bar", "Spanish"), ("Barcelona", "Spanish"), ("Flamenco", "Spanish"),
    
    # Brazilian
    ("Rio Grill", "Brazilian"), ("Carnaval", "Brazilian"),
    
    # Lebanese
    ("Cedars", "Lebanese"), ("Beirut", "Lebanese"),
    
    # Turkish
    ("Istanbul", "Turkish"), ("Bosphorus", "Turkish"),
]

def create_tables():
    """Create database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create restaurants table
    c.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cuisine TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            price_range INTEGER NOT NULL CHECK(price_range BETWEEN 1 AND 4),
            ambiance TEXT NOT NULL,
            rating REAL NOT NULL CHECK(rating BETWEEN 0 AND 5),
            address TEXT
        )
    """)
    
    # Create bookings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'cancelled', 'completed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("[OK] Tables created successfully")

def generate_restaurant_data():
    """Generate diverse restaurant data."""
    restaurants = []
    
    # Use predefined names first
    used_names = set()
    for name, cuisine in RESTAURANT_NAMES:
        if name not in used_names:
            used_names.add(name)
            location = random.choice(LOCATIONS)
            ambiance = random.choice(AMBIANCES)
            # Ensure romantic restaurants have romantic ambiance
            if "romantic" in name.lower() or "bella" in name.lower() or "intimate" in name.lower():
                ambiance = "Romantic"
            # Ensure family-friendly names have appropriate ambiance
            if "family" in name.lower() or "diner" in name.lower():
                ambiance = "Family-friendly"
            
            price_range = random.randint(1, 4)
            # Upscale restaurants should have higher price range
            if ambiance == "Upscale" or "Palace" in name or "Royal" in name:
                price_range = random.randint(3, 4)
            
            rating = round(random.uniform(3.5, 5.0), 1)
            capacity = random.randint(20, 200)
            
            address = f"{random.randint(100, 9999)} {location} Street"
            
            restaurants.append({
                "name": name,
                "cuisine": cuisine,
                "location": location,
                "capacity": capacity,
                "price_range": price_range,
                "ambiance": ambiance,
                "rating": rating,
                "address": address
            })
    
    # Fill to 75 restaurants with random combinations
    while len(restaurants) < 75:
        name = f"{random.choice(['The', 'Café', 'Restaurant', 'Bistro', 'Kitchen', 'House'])} {random.choice(['Golden', 'Royal', 'Grand', 'Elite', 'Prime', 'Noble'])} {random.choice(['Dining', 'Eatery', 'Grill', 'Place', 'Spot'])}"
        if name not in used_names:
            used_names.add(name)
            restaurants.append({
                "name": name,
                "cuisine": random.choice(CUISINES),
                "location": random.choice(LOCATIONS),
                "capacity": random.randint(20, 200),
                "price_range": random.randint(1, 4),
                "ambiance": random.choice(AMBIANCES),
                "rating": round(random.uniform(3.5, 5.0), 1),
                "address": f"{random.randint(100, 9999)} {random.choice(LOCATIONS)} Street"
            })
    
    return restaurants

def populate_restaurants():
    """Populate restaurants table with data."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if restaurants already exist
    c.execute("SELECT COUNT(*) FROM restaurants")
    count = c.fetchone()[0]
    
    if count > 0:
        print(f"[WARNING] Database already contains {count} restaurants. Skipping population.")
        print("  To repopulate, delete the database file and run this script again.")
        conn.close()
        return
    
    restaurants = generate_restaurant_data()
    
    for restaurant in restaurants:
        c.execute("""
            INSERT INTO restaurants (name, cuisine, location, capacity, price_range, ambiance, rating, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            restaurant["name"],
            restaurant["cuisine"],
            restaurant["location"],
            restaurant["capacity"],
            restaurant["price_range"],
            restaurant["ambiance"],
            restaurant["rating"],
            restaurant["address"]
        ))
    
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(restaurants)} restaurants successfully")

def main():
    """Main initialization function."""
    print("Initializing GoodFoods database...")
    print("-" * 50)
    
    create_tables()
    populate_restaurants()
    
    # Verify
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM restaurants")
    count = c.fetchone()[0]
    conn.close()
    
    print("-" * 50)
    print(f"[OK] Database initialization complete! ({count} restaurants)")

if __name__ == "__main__":
    main()

