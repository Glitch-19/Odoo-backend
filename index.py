# create_index.py - RUN THIS SCRIPT SEPARATELY
import faiss
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import os
import torch
import numpy as np
# Load the AI model
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

image_paths = [...] # List of all your product image file paths
product_ids = [...] # List of corresponding product IDs

image_embeddings = []
for path in image_paths:
    image = Image.open(path)
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = model.get_image_features(**inputs)
    image_embeddings.append(embedding.numpy().flatten())

# Create a FAISS index
dimension = len(image_embeddings[0])
index = faiss.IndexFlatL2(dimension)
index.add(np.array(image_embeddings))

# Save the index and the mapping
faiss.write_index(index, "product_image.index")
# Also save the 'product_ids' list so you can map index results back to products