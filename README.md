# 👨‍🍳 MyBestChef

An AI-powered culinary assistant and smart kitchen agent built using the **Google Agent Development Kit (ADK)**, **Google Agent Platform**, and **Vertex AI**.

![MyBestChef Demo](./demo.gif)

---

## 🌟 Features & Capabilities

MyBestChef provides an interactive culinary companion equipped with the following implemented tools:

- **📦 Firestore Pantry Inventory (`manage_pantry`)**:
  - Track, add, remove, and list pantry items stored in Google Cloud Firestore (`pantry` collection).
- **📖 Firestore Recipe Management (`search_recipes`, `get_recipe`, `add_recipe`)**:
  - Search, retrieve, and save custom structured recipes in Google Cloud Firestore (`recipes` collection).
- **🌐 Public Online Recipe Search (`fetch_public_recipes`)**:
  - Query external recipes from TheMealDB public REST API when recipes are not present in local inventory.
- **⚖️ Recipe Ingredient Scaling (`scale_recipe_ingredients`)**:
  - Dynamically recalculate ingredient quantities for custom target serving sizes.
- **🖼️ Plated Dish Image Generation (`generate_dish_image`)**:
  - Generate high-resolution dish photo previews using `gemini-3.1-flash-lite-image` in the `global` region and upload JPEG bytes to a public Google Cloud Storage bucket.
- **🎥 Recipe Video Generation (`generate_recipe_video`)**:
  - Generate short culinary video previews using Google's Omni model `gemini-omni-flash-preview` in the `global` region, saving MP4 artifacts to ADK `ToolContext` and uploading to Cloud Storage.
- **🧠 Cross-Session Memory (`PreloadMemoryTool`)**:
  - Remember user culinary facts, preferences, and dietary restrictions across conversations via Vertex AI Memory Bank (`VertexAiMemoryBankService`).
- **🎨 Dynamic A2UI Display Cards (`A2uiSchemaManager`)**:
  - Emit structured A2UI v0.8 display cards (Card, Column, Row, Text, Image, Icon) rendered natively in the chat interface.
- **💻 Python Sandbox Execution (`AgentEngineSandboxCodeExecutor`)**:
  - Safely execute Python code in an isolated Agent Engine sandbox for custom data processing or calculations.

---

## 🛠️ Google Cloud Services & Architecture

| Layer | Component | Service |
|---|---|---|
| **Framework** | Agent Development Kit | Google ADK (`google-adk`) |
| **Model Runtime** | Primary LLM | Vertex AI (`gemini-2.5-flash`) |
| **Multimodal Generation** | Image & Video Generation | Vertex AI (`gemini-3.1-flash-lite-image`, `gemini-omni-flash-preview`) |
| **Database** | NoSQL Data Store | Google Cloud Firestore |
| **Object Storage** | Media Assets Bucket | Google Cloud Storage |
| **Long-Term Memory** | Memory Bank | Vertex AI Memory Bank |
| **Frontend Proxy** | FastAPI Middleware | `a2a-sdk` (A2A Protocol Proxy) |
| **User Interface** | Chat Web Interface | HTML5 / Vanilla CSS with built-in A2UI renderer |

---

## 🚀 Setup & Local Execution Instructions

### Prerequisites
- Python 3.12+
- `uv` package manager installed
- Google Cloud SDK (`gcloud`) authenticated

### 1. Installation
Clone the repository and install dependencies using `uv`:
```bash
uv pip install -r requirements.txt
```

### 2. Google Cloud Authentication
Authenticate with Application Default Credentials:
```bash
gcloud auth application-default login
```

### 3. Running the ADK Playground Locally
To launch the interactive ADK Web development playground with hot-reloading:
```bash
uv run adk web . --port 8080 --reload_agents
```

### 4. Running the Frontend Proxy Locally
To run the web chat interface and A2A proxy server locally:
```bash
cd frontend
uv pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<LOCATION>/reasoningEngines/<RESOURCE_ID>"
export AGENT_DIRECTORY="app"
uv run python main.py
```
