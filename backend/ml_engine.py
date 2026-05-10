# ml_engine.py
import os
import pickle
import numpy as np
from config import Config

# Detect if we're running on Render (production)
IS_PRODUCTION = os.getenv('RENDER', False)

# Models will only load locally — not on Render
issue_type_model = None
priority_model = None
tfidf_vectorizer = None
image_model = None


def load_models():
    """Load ML models — only in local development"""
    global issue_type_model, priority_model
    global tfidf_vectorizer, image_model

    if IS_PRODUCTION:
        print(
            "🌐 Running in production — using Claude Vision " +
            "instead of local ML models"
        )
        return

    try:
        # Load text models
        with open(Config.ISSUE_TYPE_MODEL, 'rb') as f:
            issue_type_model = pickle.load(f)
            print("✅ Issue Type Model loaded")

        with open(Config.PRIORITY_MODEL, 'rb') as f:
            priority_model = pickle.load(f)
            print("✅ Priority Model loaded")

        with open(Config.TFIDF_VECTORIZER, 'rb') as f:
            tfidf_vectorizer = pickle.load(f)
            print("✅ TF-IDF Vectorizer loaded")

        # Load image model
        try:
            from tensorflow.keras.models import load_model
            image_model = load_model(Config.IMAGE_MODEL)
            print("✅ Image Model loaded")
        except Exception as e:
            print(f"⚠️ Image model skipped: {e}")
            image_model = None

        print("\n✅ All ML models loaded successfully!")

    except Exception as e:
        print(f"❌ Error loading models: {e}")
        print(
            "⚠️ Continuing without local models — " +
            "Claude Vision will be used"
        )


def classify_issue_text(description):
    """Classify text using local ML models"""
    if issue_type_model is None or tfidf_vectorizer is None:
        # Fallback if models aren't loaded
        return {
            'issue_type': 'Administrative',
            'priority': 'Medium'
        }

    try:
        text_vector = tfidf_vectorizer.transform([description])
        issue_type = issue_type_model.predict(text_vector)[0]
        priority = priority_model.predict(text_vector)[0]
        return {
            'issue_type': issue_type,
            'priority': priority
        }
    except Exception as e:
        print(f"❌ Text classification error: {e}")
        return {
            'issue_type': 'Administrative',
            'priority': 'Medium'
        }


def classify_issue_image(image_path):
    """Classify image using local image model"""
    if image_model is None:
        return {'damage_detected': False}

    try:
        from PIL import Image
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        prediction = image_model.predict(img_array, verbose=0)
        damage_score = float(prediction[0][0])
        return {'damage_detected': damage_score > 0.5}
    except Exception as e:
        print(f"❌ Image classification error: {e}")
        return {'damage_detected': False}


def classify_issue(description=None, image_path=None):
    """Main classification function"""
    result = {
        'issue_type': 'Administrative',
        'priority': 'Medium',
        'damage_detected': False
    }

    if description:
        text_result = classify_issue_text(description)
        result['issue_type'] = text_result['issue_type']
        result['priority'] = text_result['priority']

    if image_path:
        image_result = classify_issue_image(image_path)
        result['damage_detected'] = image_result['damage_detected']

    return result