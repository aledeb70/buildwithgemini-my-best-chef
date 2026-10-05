# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcoded GCP Project ID string to prevent Agent Platform project number resolution issue
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-fca0414a4718"
GCS_BUCKET_NAME = "my-best-chef-media-qwiklabs-gcp-03-fca0414a4718"
db = firestore.Client(project=FIRESTORE_PROJECT_ID)

# Read remote Agent Engine ID from deployment_metadata.json for sandboxed Python execution & Memory Bank
deployment_meta_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
agent_engine_resource_name = None
if os.path.exists(deployment_meta_path):
    try:
        with open(deployment_meta_path, "r") as f:
            meta = json.load(f)
            agent_engine_resource_name = meta.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Could not read deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and preferences to Vertex AI Memory Bank after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory service not available or skipped: {e}")
    return None


def memory_service_builder():
    """Memory Bank service builder for Vertex AI Agent Engine deployments."""
    memory_bank_id = "8350677563261059072"
    if agent_engine_resource_name:
        memory_bank_id = agent_engine_resource_name.split("/")[-1]
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=memory_bank_id,
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are MyBestChef, a personal culinary assistant. "
        "Use your tools to search local Firestore recipes, search public online recipes via TheMealDB, "
        "retrieve recipe details, save new recipes, manage pantry inventory, "
        "scale ingredient quantities for different serving sizes, and generate visual plated dish previews. "
        "You can also execute Python code in a safe Agent Engine sandbox to run complex calculations or custom data processing. "
        "You remember the user's stated preferences, dietary restrictions, and culinary facts across conversations."
    ),
    workflow_description="Analyze the culinary or recipe request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


def fetch_public_recipes(ingredient_or_dish: str = "") -> str:
    """Fetch external online recipes from TheMealDB public API.

    Args:
        ingredient_or_dish: Name of dish or ingredient to search online (e.g. 'pasta', 'chicken', 'salmon').

    Returns:
        List of online recipe titles, categories, cuisines, and instructions.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    term = ingredient_or_dish.strip() or "chicken"
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={urllib.parse.quote(term)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MyBestChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meals = data.get("meals")
            if not meals:
                return f"No online recipes found for '{term}'."

            results = []
            for meal in meals[:3]:  # Top 3 results
                results.append({
                    "id": meal.get("idMeal"),
                    "title": meal.get("strMeal"),
                    "category": meal.get("strCategory"),
                    "cuisine": meal.get("strArea"),
                    "instructions": (meal.get("strInstructions") or "")[:250] + "...",
                    "thumbnail": meal.get("strMealThumb"),
                })
            return str(results)
    except Exception as e:
        return f"Error fetching public online recipes: {e}"


def search_recipes(query: str = "", dietary_tag: str = "") -> str:
    """Search recipes in the Firestore database by title, cuisine, or dietary tag.

    Args:
        query: Optional keyword to match in title or cuisine (e.g. 'Italian', 'Chicken').
        dietary_tag: Optional tag filter (e.g. 'gluten-free', 'vegan', 'keto').

    Returns:
        A list of matching recipe summaries.
    """
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()

    matches = []
    q_lower = query.lower().strip()
    tag_lower = dietary_tag.lower().strip()

    for doc in docs:
        data = doc.to_dict()
        title = data.get("title", "")
        cuisine = data.get("cuisine", "")
        tags = [t.lower() for t in data.get("dietary_tags", [])]

        match_query = not q_lower or (q_lower in title.lower() or q_lower in cuisine.lower())
        match_tag = not tag_lower or (tag_lower in tags)

        if match_query and match_tag:
            matches.append({
                "id": doc.id,
                "title": title,
                "cuisine": cuisine,
                "prep_time_minutes": data.get("prep_time_minutes"),
                "servings": data.get("servings"),
                "dietary_tags": data.get("dietary_tags", []),
                "calories_per_serving": data.get("calories_per_serving"),
            })

    if not matches:
        return f"No recipes found matching query '{query}' and tag '{dietary_tag}'."
    return str(matches)


def get_recipe(recipe_id: str) -> str:
    """Retrieve full details for a specific recipe by ID from the Firestore database.

    Args:
        recipe_id: The document ID of the recipe (e.g. 'recipe-001').

    Returns:
        Full recipe dictionary with ingredients and instructions, or an error string.
    """
    doc_ref = db.collection("recipes").document(recipe_id.strip())
    doc = doc_ref.get()
    if not doc.exists:
        return f"Recipe with ID '{recipe_id}' not found."
    return str(doc.to_dict())


def add_recipe(
    title: str,
    cuisine: str,
    prep_time_minutes: int,
    servings: int,
    ingredients: list[str],
    instructions: list[str],
    dietary_tags: list[str],
    calories_per_serving: int = 0
) -> str:
    """Add a new recipe to the Firestore database.

    Args:
        title: Title of the recipe.
        cuisine: Cuisine type (e.g. 'Italian', 'Mexican').
        prep_time_minutes: Preparation/cooking time in minutes.
        servings: Number of servings.
        ingredients: List of ingredients with quantities.
        instructions: Step-by-step cooking instructions.
        dietary_tags: List of tags (e.g. ['gluten-free', 'vegan']).
        calories_per_serving: Estimated calories per serving.

    Returns:
        A success message with the created recipe ID.
    """
    doc_id = f"recipe-{uuid.uuid4().hex[:6]}"
    recipe_data = {
        "id": doc_id,
        "title": title,
        "cuisine": cuisine,
        "prep_time_minutes": prep_time_minutes,
        "servings": servings,
        "ingredients": ingredients,
        "instructions": instructions,
        "dietary_tags": dietary_tags,
        "calories_per_serving": calories_per_serving,
    }
    db.collection("recipes").document(doc_id).set(recipe_data)
    return f"Successfully saved recipe '{title}' to Firestore with ID: {doc_id}"


def manage_pantry(action: str, item: str = "", quantity: str = "") -> str:
    """Manage the user's pantry inventory in the Firestore database.

    Args:
        action: The operation to perform ('list', 'add', 'remove', 'clear').
        item: The name of the pantry item (e.g., 'heavy cream', 'spinach', 'chickpeas').
        quantity: Optional amount or quantity description (e.g., '2 cups', '1 lb', '3 cans').

    Returns:
        Current pantry stock list or a confirmation message of the update.
    """
    pantry_ref = db.collection("pantry")
    act = action.lower().strip()

    if act == "list":
        docs = pantry_ref.stream()
        items = []
        for doc in docs:
            d = doc.to_dict()
            items.append({"item": d.get("item", doc.id), "quantity": d.get("quantity", "unspecified")})
        if not items:
            return "Your pantry is currently empty."
        return str(items)

    elif act == "add":
        if not item:
            return "Error: Please specify an item to add to the pantry."
        doc_id = item.lower().strip().replace(" ", "_")
        pantry_ref.document(doc_id).set({
            "item": item.strip(),
            "quantity": quantity.strip() if quantity else "available",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        return f"Added/updated '{item}' ({quantity or 'available'}) in your pantry."

    elif act == "remove":
        if not item:
            return "Error: Please specify an item to remove from the pantry."
        doc_id = item.lower().strip().replace(" ", "_")
        pantry_ref.document(doc_id).delete()
        return f"Removed '{item}' from your pantry."

    elif act == "clear":
        docs = pantry_ref.stream()
        for doc in docs:
            doc.reference.delete()
        return "Cleared all items from your pantry."

    else:
        return f"Unknown action '{action}'. Supported actions are: 'list', 'add', 'remove', 'clear'."


def scale_recipe_ingredients(ingredients: list[str], original_servings: int, target_servings: int) -> str:
    """Scale recipe ingredient quantities from original servings to target servings.

    Args:
        ingredients: List of ingredient strings (e.g. ['2 lbs chicken breast', '1 cup heavy cream']).
        original_servings: Base number of servings for the recipe (e.g. 4).
        target_servings: Desired number of servings (e.g. 6).

    Returns:
        List of scaled ingredient strings.
    """
    if original_servings <= 0 or target_servings <= 0:
        return "Error: Servings must be greater than zero."

    ratio = target_servings / original_servings
    scaled = []

    for ing in ingredients:
        parts = ing.strip().split(" ", 1)
        if len(parts) < 2:
            scaled.append(ing)
            continue
        try:
            val = float(parts[0])
            new_val = val * ratio
            fmt_val = f"{int(new_val)}" if new_val.is_integer() else f"{round(new_val, 2)}"
            scaled.append(f"{fmt_val} {parts[1]}")
        except ValueError:
            scaled.append(f"{ing} (scaled {ratio:.2f}x)")

    return str(scaled)


async def generate_dish_image(dish_name: str, description: str = "", tool_context: ToolContext = None) -> str:
    """Generate a visual image preview for a dish using gemini-3.1-flash-lite-image in global region.

    Args:
        dish_name: Name of the dish or culinary item (e.g. 'Gluten-Free Creamy Tuscan Chicken').
        description: Brief optional presentation details.

    Returns:
        Public Cloud Storage HTTPS URL of the generated image.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        prompt = f"A gourmet, high-resolution food photo of {dish_name}. {description}".strip()

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            )
        )

        image_bytes = None
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    break
            if image_bytes:
                break

        if not image_bytes:
            return "Error: Image generation produced no image bytes."

        # 1. Save artifact to ToolContext for Playground Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            artifact_filename = f"dish_{uuid.uuid4().hex[:6]}.jpg"
            await tool_context.save_artifact(artifact_filename, artifact_part)

        # 2. Upload same image bytes to public Cloud Storage bucket
        object_name = f"dishes/dish_{uuid.uuid4().hex[:8]}.jpg"
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

    except Exception as e:
        return f"Error generating dish image: {e}"


async def generate_recipe_video(item_name: str, description: str = "", tool_context: ToolContext = None) -> str:
    """Generate a short video preview for a culinary item or dish using gemini-omni-flash-preview in global region.

    Args:
        item_name: Name of the culinary item or dish (e.g. 'Sizzling Garlic Butter Steak' or 'Strawberry Cheesecake').
        description: Brief description of the scene, cooking motion, or plating.

    Returns:
        Public Cloud Storage HTTPS URL of the generated MP4 video.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        prompt = f"A short, high-resolution food video showing {item_name}. {description}".strip()

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
            raw_data = interaction.output_video.data
            video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data

        if not video_bytes:
            return "Error: Video generation produced no video bytes."

        # 1. Save artifact to ToolContext for Playground Artifacts panel
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
            artifact_filename = f"recipe_video_{uuid.uuid4().hex[:6]}.mp4"
            await tool_context.save_artifact(artifact_filename, artifact_part)

        # 2. Upload video bytes to public Cloud Storage bucket
        object_name = f"videos/recipe_video_{uuid.uuid4().hex[:8]}.mp4"
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

    except Exception as e:
        return f"Error generating recipe video: {e}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        search_recipes,
        fetch_public_recipes,
        get_recipe,
        add_recipe,
        manage_pantry,
        scale_recipe_ingredients,
        generate_dish_image,
        generate_recipe_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
