from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
import random, os, uuid, time, logging
try:
    import google.generativeai as genai
except ImportError:
    genai = None
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from PIL import Image
import io

# Configure Google Gemini API
if genai:
    genai.configure(api_key="AIzaSyDsn6kvbVizsBuDvIjzGWnbcrBMaNXUTNQ")  # Provided API key

# Configure OpenAI API (replace with your key)
client = None
if OpenAI:
    api_key = "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"
    if api_key != "your_openai_api_key_here":  # Only initialize if a real key is provided
        try:
            client = OpenAI(api_key=api_key, max_retries=0)  # Disable retries to avoid issues
        except Exception as e:
            logging.error(f"OpenAI client error: {e}")
            client = None

app = Flask(__name__, static_folder='static')
app.secret_key = 'haunted_secret_key_123'  # Change this to a secure key in production

# In-memory storage for feedbacks (for simplicity; use a database in production)
feedbacks = []

def generate_story(name: str, theme: str, length: int = 5, country: str = 'random', horror_level: str = 'normal horror'):
    countries = ["Afghanistan", "Algeria", "Argentina", "Australia", "Brazil", "Canada", "China", "Egypt", "France", "Germany", "India", "Italy", "Japan", "Mexico", "Russia", "South Africa", "Spain", "Thailand", "UK", "USA", "Vietnam"]
    if country == 'random':
        country = random.choice(countries)
    try:
        # Use Google Gemini to generate story
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        # Randomly select a horror subgenre for diversity
        subgenres = ["psychological", "supernatural", "slasher", "gothic", "cosmic horror", "body horror", "folk horror", "vampiric", "zombie apocalypse", "possession", "time loop", "alternate reality"]
        subgenre = random.choice(subgenres)

        # Adjust intensity based on horror_level
        intensity_modifier = ""
        if horror_level == 'middle horror':
            intensity_modifier = "Make it moderately intense with some graphic elements."
        elif horror_level == 'extremely horror':
            intensity_modifier = "Make it extremely intense with graphic, terrifying details and high suspense."

        prompt = f"Write a unique {subgenre} horror story consisting of exactly {length} paragraphs about {name} in a {theme} setting set in {country}. Make it spooky and atmospheric with unexpected twists and diverse elements. {intensity_modifier} Each paragraph should be 2-3 sentences long and introduce new, original ideas. Separate each paragraph with a blank line (double newline). Ensure no repeated phrases or lines. Make each story fresh and different from typical haunted tales, varying in plot structure, characters, and endings."
        response = model.generate_content(prompt)
        story_text = response.text.strip()

        # Split into paragraphs by double newline
        paragraphs = [p.strip() for p in story_text.split('\n\n') if p.strip()]

        # Ensure we have exactly length paragraphs
        if len(paragraphs) < length:
            additional_needed = length - len(paragraphs)
            additional_prompt = f"Continue the haunted story with exactly {additional_needed} more paragraphs. Make it spooky and atmospheric. {intensity_modifier} Each paragraph 2-3 sentences. Separate with blank lines. Avoid repetition."
            additional_response = model.generate_content(additional_prompt)
            additional_text = additional_response.text.strip()
            additional_paras = [p.strip() for p in additional_text.split('\n\n') if p.strip()]
            paragraphs.extend(additional_paras[:additional_needed])

        title = f"The Tale of {name} from {country}"
        return {"title": title, "paragraphs": paragraphs[:length]}
    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        # Fallback: Generate a simple fallback story if API fails
        if "quota" in str(e).lower():
            paras = [f"The API quota has been exceeded. Please try again later." for _ in range(length)]
        else:
            paras = [f"In the depths of the unknown, {name} encountered horrors beyond imagination." for _ in range(length)]
        title = f"The Tale of {name} from {country}"
        return {"title": title, "paragraphs": paras}

def generate_horror_image(story_text: str):
    try:
        # Extract key elements from story for prompt
        # Simple extraction: take first 200 chars as basis
        story_summary = story_text[:200] + "..." if len(story_text) > 200 else story_text
        prompt = f"Create a dark, eerie, realistic horror-themed image based on this story: {story_summary}. Visually represent the main scene, characters, ghosts, and environment. Include atmospheric effects such as mist, shadows, flickering lights, and haunted surroundings. Maintain a cinematic horror tone with fine details. High-quality, 1024x1024, suitable for web display."
        if client:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            # Download and save the image
            import requests
            img_response = requests.get(image_url)
            os.makedirs('static/images', exist_ok=True)
            filename = f"horror_{uuid.uuid4().hex}.png"
            filepath = os.path.join('static/images', filename)
            with open(filepath, 'wb') as f:
                f.write(img_response.content)
            return f"/static/images/{filename}"
        else:
            # Fallback if no OpenAI
            return None
    except Exception as e:
        logging.error(f"Image generation error: {e}")
        return None

@app.route('/generate_story', methods=['POST'])
def api_generate_story():
    data = request.get_json() or {}
    name = data.get('name', 'Anonymous')
    theme = data.get('theme', 'default')
    try:
        length = int(data.get('length', 5))
    except ValueError:
        length = 5
    country = data.get('country', 'random')
    horror_level = data.get('horror_level', 'normal horror')
    story = generate_story(name, theme, length, country, horror_level)
    # Format the story as a string for the textarea
    story_text = story['title'] + '\n\n'
    for para in story['paragraphs']:
        story_text += para + '\n\n'
    return jsonify({"ok": True, "story": story_text})

@app.route('/generate_image', methods=['POST'])
def api_generate_image():
    data = request.get_json() or {}
    story_text = data.get('story_text', '')
    if not story_text:
        return jsonify({"ok": False, "error": "No story text provided"})
    image_url = generate_horror_image(story_text)
    if image_url:
        return jsonify({"ok": True, "image_url": image_url})
    else:
        return jsonify({"ok": False, "error": "Failed to generate image"})

@app.route('/analyze_peaks', methods=['POST'])
def api_analyze_peaks():
    data = request.get_json() or {}
    story_text = data.get('story_text', '')
    if not story_text:
        return jsonify({"ok": False, "error": "No story text provided"})
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        prompt = f"Analyze this horror story and identify the paragraph indices (starting from 0) where the most intense, supernatural, or jumpscare-worthy moments occur. Return only a JSON array of integers representing the paragraph numbers. Story:\n\n{story_text}"
        response = model.generate_content(prompt)
        peaks_text = response.text.strip()
        # Extract JSON array from response
        import re
        json_match = re.search(r'\[.*\]', peaks_text)
        if json_match:
            import json
            peaks = json.loads(json_match.group(0))
            return jsonify({"ok": True, "peaks": peaks})
        else:
            return jsonify({"ok": False, "error": "Failed to parse peaks"})
    except Exception as e:
        logging.error(f"Peaks analysis error: {e}")
        return jsonify({"ok": False, "error": "Analysis failed"})

@app.route('/')
def index():
    return send_from_directory('../frontend', 'login.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name')
    email = request.form.get('email')
    if name and email:
        session['user'] = {'name': name, 'email': email}
        return redirect(url_for('welcome'))
    return redirect(url_for('index'))

@app.route('/welcome')
def welcome():
    if 'user' not in session:
        return redirect(url_for('index'))
    return send_from_directory('../frontend', 'welcome.html')

@app.route('/main')
def main():
    if 'user' not in session:
        return redirect(url_for('index'))
    return send_from_directory('../frontend', 'main.html')

@app.route('/exit')
def exit():
    if 'user' not in session:
        return redirect(url_for('index'))
    return send_from_directory('../frontend', 'exit.html')

@app.route('/feedback')
def feedback():
    if 'user' not in session:
        return redirect(url_for('index'))
    return send_from_directory('../frontend', 'feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user' not in session:
        return jsonify({"ok": False, "error": "Not logged in"})
    data = request.get_json() or {}
    rating = data.get('rating')
    feedback_text = data.get('feedback')
    if not rating or not feedback_text:
        return jsonify({"ok": False, "error": "Missing rating or feedback"})
    feedbacks.append({
        "rating": rating,
        "feedback": feedback_text,
        "timestamp": time.time(),
        "user": session['user']['name']
    })
    return jsonify({"ok": True})

@app.route('/get_feedbacks', methods=['GET'])
def get_feedbacks():
    if 'user' not in session:
        return jsonify({"ok": False, "error": "Not logged in"})
    return jsonify({"ok": True, "feedbacks": feedbacks})

if __name__ == '__main__':
    app.run(debug=True)
