import os
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-fca0414a4718"

# Hardcode project ID to ensure Firestore client uses project ID string
db = firestore.Client(project=PROJECT_ID)

SEEDED_RECIPES = [
    {
        "id": "recipe-001",
        "title": "Gluten-Free Creamy Tuscan Chicken",
        "cuisine": "Italian",
        "prep_time_minutes": 25,
        "servings": 4,
        "ingredients": [
            "2 lbs chicken breast",
            "1 cup heavy cream",
            "1/2 cup sun-dried tomatoes",
            "2 cups fresh spinach",
            "3 cloves garlic minced",
            "2 tbsp olive oil",
            "Salt and black pepper to taste"
        ],
        "instructions": [
            "Season chicken breasts with salt and pepper.",
            "Heat olive oil in a skillet over medium-high heat and sear chicken until golden brown (6-8 mins per side).",
            "Remove chicken, stir in minced garlic, sun-dried tomatoes, and heavy cream.",
            "Add spinach and simmer until wilted and sauce is creamy.",
            "Return chicken to skillet and coat with sauce before serving."
        ],
        "dietary_tags": ["gluten-free", "keto", "high-protein"],
        "calories_per_serving": 480
    },
    {
        "id": "recipe-002",
        "title": "Vegan Loaded Avocado Grain Bowl",
        "cuisine": "Mediterranean",
        "prep_time_minutes": 20,
        "servings": 2,
        "ingredients": [
            "1 cup cooked quinoa",
            "1 ripe avocado sliced",
            "1/2 cup canned chickpeas rinsed",
            "1/2 cup cherry tomatoes halved",
            "1/2 cup cucumber diced",
            "2 tbsp tahini dressing",
            "1 tbsp lemon juice"
        ],
        "instructions": [
            "Divide cooked quinoa between two serving bowls.",
            "Top with sliced avocado, chickpeas, cherry tomatoes, and cucumber.",
            "Drizzle with tahini dressing and fresh lemon juice.",
            "Garnish with toasted sesame seeds if desired."
        ],
        "dietary_tags": ["vegan", "vegetarian", "dairy-free", "gluten-free"],
        "calories_per_serving": 410
    },
    {
        "id": "recipe-003",
        "title": "Keto Lemon Herb Grilled Salmon",
        "cuisine": "Seafood",
        "prep_time_minutes": 15,
        "servings": 2,
        "ingredients": [
            "2 salmon fillets (6 oz each)",
            "2 tbsp unsalted butter melted",
            "1 tbsp fresh lemon juice",
            "1 tsp dried dill or fresh parsley",
            "2 cloves garlic minced",
            "1/2 tsp sea salt"
        ],
        "instructions": [
            "Preheat grill or skillet to medium-high heat.",
            "Whisk melted butter, lemon juice, minced garlic, dill, and salt together.",
            "Brush salmon fillets with the lemon herb mixture.",
            "Grill skin-side down for 4-5 minutes, flip carefully, and cook another 3-4 minutes until flaky."
        ],
        "dietary_tags": ["keto", "gluten-free", "low-carb", "high-protein"],
        "calories_per_serving": 520
    },
    {
        "id": "recipe-004",
        "title": "Vegetarian Lentil & Veggie Curry",
        "cuisine": "Indian",
        "prep_time_minutes": 30,
        "servings": 4,
        "ingredients": [
            "1 cup brown or green lentils rinsed",
            "1 can (14 oz) coconut milk",
            "1 can (14 oz) diced tomatoes",
            "1 onion diced",
            "1 tbsp yellow curry powder",
            "1 cup diced carrots and sweet potato"
        ],
        "instructions": [
            "Sauté onion, carrots, and sweet potato in a pot until softened (5 mins).",
            "Add curry powder and stir for 1 minute until fragrant.",
            "Pour in brown lentils, coconut milk, and diced tomatoes.",
            "Simmer covered on low heat for 25 minutes until lentils and veggies are tender."
        ],
        "dietary_tags": ["vegetarian", "vegan", "gluten-free", "high-fiber"],
        "calories_per_serving": 380
    }
]

SEEDED_PANTRY = [
    {"item": "Olive Oil", "quantity": "1 bottle"},
    {"item": "Garlic", "quantity": "1 bulb"},
    {"item": "Spinach", "quantity": "1 bag (8 oz)"},
    {"item": "Chickpeas", "quantity": "2 cans"},
    {"item": "Quinoa", "quantity": "1 bag (16 oz)"},
    {"item": "Heavy Cream", "quantity": "1 pint"},
]

def seed():
    print(f"Seeding Firestore collection 'recipes' in project '{PROJECT_ID}'...")
    recipes_ref = db.collection("recipes")
    for item in SEEDED_RECIPES:
        doc_id = item["id"]
        recipes_ref.document(doc_id).set(item)
        print(f"  ✓ Seeded recipe: {doc_id} ({item['title']})")

    print(f"\nSeeding Firestore collection 'pantry' in project '{PROJECT_ID}'...")
    pantry_ref = db.collection("pantry")
    for p in SEEDED_PANTRY:
        doc_id = p["item"].lower().replace(" ", "_")
        pantry_ref.document(doc_id).set(p)
        print(f"  ✓ Seeded pantry item: {p['item']} ({p['quantity']})")

    print("\nFirestore seeding complete!")

if __name__ == "__main__":
    seed()
