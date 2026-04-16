import requests
import json
import base64
import time
import os

print("Fetching test image...")
# Find any image in the known_faces directory to use as a test image
test_img = None
for root, dirs, files in os.walk("known_faces"):
    for f in files:
        if f.endswith(".jpg"):
            test_img = os.path.join(root, f)
            break
    if test_img:
        break

if not test_img:
    print("Could not find a test image in known_faces")
    exit(1)

print(f"Using test image: {test_img}")
with open(test_img, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode('utf-8')

print("Sending request to Ollama...")
try:
    start_time = time.time()
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "moondream",
            "prompt": "Describe this scene. Say if you see fire.",
            "images": [img_b64],
            "stream": True,
            "options": {
                "temperature": 0.1,
                "num_predict": 40
            }
        },
        stream=True
    )
    
    print("Streaming response:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            print(data.get("response", ""), end="", flush=True)
            if data.get("done"):
                break
    print(f"\nDone in {time.time() - start_time:.2f} seconds!")
except Exception as e:
    print(f"Error: {e}")
