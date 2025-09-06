# ai_agents.py
from PIL import Image
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from transformers import CLIPModel, CLIPProcessor
import faiss
import torch
def analyze_condition(image_file):
    """
    Analyzes an image to determine its condition.
    For the hackathon, this is a simplified simulation.
    A real implementation would use a trained TensorFlow/Keras model.
    """
    try:
        with Image.open(image_file.stream) as img:
            # Simple logic: brighter images are in 'Excellent' condition
            brightness = np.mean(img)
            if brightness > 150:
                condition = "Excellent"
            elif brightness > 75:
                condition = "Good"
            else:
                condition = "Needs Repair"

            # Authenticity would require a much more complex model
            authenticity_score = 0.95 # Simulate a high score
            return {"condition": condition, "authenticity_score": authenticity_score}
    except Exception as e:
        return {"error": str(e)}
    
data = {'category': [1, 2, 1, 3, 2], 'condition': [3, 2, 3, 1, 2], 'price': [50, 200, 65, 15, 150]}
df = pd.DataFrame(data)
# 2. Train model
X = df[['category', 'condition']]
y = df['price']
price_model = RandomForestRegressor(n_estimators=100, random_state=42)
price_model.fit(X.values, y.values)
# --- End of offline training ---

def suggest_price(category, condition):
    """Predicts price based on category and condition."""
    # In a real app, you'd load a pre-trained model file (e.g., a .pkl)
    # For simplicity, we're using the model trained above.
    # Mapping for the function
    cat_map = {'electronics': 1, 'fashion': 2, 'home': 3}
    cond_map = {'Excellent': 3, 'Good': 2, 'Needs Repair': 1}

    try:
        cat_num = cat_map.get(category, 1)
        cond_num = cond_map.get(condition, 2)
        predicted_price = price_model.predict([[cat_num, cond_num]])
        return {"suggested_price": round(predicted_price[0], 2)}
    except Exception as e:
        return {"error": str(e)}
    
# ai_agents.py

ECO_DATA = {
    "t-shirt": {"co2_kg": 6, "water_liters": 2700},
    "smartphone": {"co2_kg": 80, "waste_kg": 0.5},
    "jeans": {"co2_kg": 33, "water_liters": 3781},
    "laptop": {"co2_kg": 250, "water_liters": 190000}
}

def get_eco_impact(category):
    """Looks up the environmental impact for a product category."""
    category_key = category.lower()
    if category_key in ECO_DATA:
        return {"status": "success", "data": ECO_DATA[category_key]}
    return {"status": "error", "message": "No data for this category"}


interactions_data = [
    (1, 101, 5), (1, 102, 1), (2, 101, 5), (2, 103, 1),
    (3, 102, 5), (3, 104, 1), (4, 101, 1), (4, 103, 5)
]
df = pd.DataFrame(interactions_data, columns=['user_id', 'product_id', 'score'])

# 2. Create a user-item matrix
user_item_matrix = df.pivot(index='user_id', columns='product_id', values='score').fillna(0)

# 3. Configure the model to find similar users
# We use cosine similarity to find users who rated items similarly
user_similarity_model = NearestNeighbors(metric='cosine', algorithm='brute')
user_similarity_model.fit(user_item_matrix.values)
# --- End of model training ---

def get_recommendations(user_id):
    """
    Finds users similar to the given user and recommends products
    they liked.
    """
    try:
        # Find the 3 most similar users (including the user themselves)
        distances, indices = user_similarity_model.kneighbors(
            user_item_matrix.loc[user_id].values.reshape(1, -1),
            n_neighbors=3
        )

        recommendations = set()
        # Get items from similar users
        for i in range(1, len(indices.flatten())):
            similar_user_id = user_item_matrix.index[indices.flatten()[i]]
            # Get products the similar user interacted with strongly (score > 3)
            liked_products = user_item_matrix.loc[similar_user_id]
            liked_products = liked_products[liked_products > 3].index.tolist()
            recommendations.update(liked_products)

        # Filter out items the original user has already seen
        seen_products = user_item_matrix.loc[user_id]
        seen_products = seen_products[seen_products > 0].index.tolist()
        final_recs = list(recommendations - set(seen_products))

        return {"user_id": user_id, "recommended_product_ids": final_recs}
    except KeyError:
        return {"error": "User ID not found or has no interactions"}, 404
    except Exception as e:
        return {"error": str(e)}, 500
    
# ai_agents.py
# ... (imports from above)

# --- Load the model and index once when the app starts ---
SEARCH_MODEL = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
SEARCH_PROCESSOR = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
IMAGE_INDEX = faiss.read_index("product_image.index")
PRODUCT_ID_MAP = [...] # Load your saved list of product IDs

def find_similar_images(image_file, top_k=5):
    """Finds the top_k most similar images from the index."""
    try:
        # 1. Create embedding for the uploaded image
        image = Image.open(image_file.stream)
        inputs = SEARCH_PROCESSOR(images=image, return_tensors="pt")
        with torch.no_grad():
            embedding = SEARCH_MODEL.get_image_features(**inputs)

        # 2. Search the FAISS index
        distances, indices = IMAGE_INDEX.search(embedding.numpy(), top_k)

        # 3. Map indices back to product IDs
        results = [PRODUCT_ID_MAP[i] for i in indices[0]]

        return {"similar_product_ids": results}
    except Exception as e:
        return {"error": str(e)}, 500