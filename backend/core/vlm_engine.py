"""
VLM Engine - Uses Ollama with a vision model for hazard/activity detection.
"""
import io
import cv2
import time
import json
import base64
import logging
import requests
import numpy as np

logger = logging.getLogger(__name__)


class VLMEngine:
    """Vision Language Model engine for scene analysis and hazard detection."""

    def __init__(self, ollama_url="http://localhost:11434", model="moondream", prompt=""):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.prompt = prompt
        self._available = False

    def initialize(self):
        """Check if Ollama is running and the model is available."""
        try:
            # Check Ollama is running
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                logger.warning("Ollama is not responding")
                return False

            # Check if our model is available
            models = resp.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]
            
            if self.model not in model_names:
                logger.info(f"Model '{self.model}' not found. Available: {model_names}")
                logger.info(f"Pulling model '{self.model}'... This may take a few minutes.")
                
                # Pull the model
                pull_resp = requests.post(
                    f"{self.ollama_url}/api/pull",
                    json={"name": self.model},
                    timeout=600,
                    stream=True
                )
                
                for line in pull_resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            if "pulling" in status or "downloading" in status:
                                logger.info(f"  {status}")
                        except:
                            pass
                
                logger.info(f"Model '{self.model}' pulled successfully")

            self._available = True
            logger.info(f"VLM Engine initialized with model: {self.model}")
            return True

        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to Ollama. VLM analysis will be disabled.")
            logger.warning("Start Ollama with: 'ollama serve' and pull the model with: 'ollama pull moondream'")
            return False
        except Exception as e:
            logger.error(f"VLM initialization error: {e}")
            return False

    def analyze_frame(self, frame):
        """
        Analyze a frame using the VLM for hazard detection.
        
        Returns dict:
        {"alert": bool, "type": str, "confidence": float, "description": str}
        """
        if not self._available:
            return {"alert": False, "type": "NONE", "confidence": 0.0,
                    "description": "VLM not available"}

        try:
            # Encode frame to base64
            # Resize for faster inference
            small_frame = cv2.resize(frame, (320, 240))
            _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            img_base64 = base64.b64encode(buffer).decode('utf-8')

            # Use a shorter, faster prompt
            fast_prompt = (
                "Describe this scene in one sentence. "
                "If you see fire, smoke, weapon, fighting, or fallen person, say so explicitly."
            )

            # Call Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": fast_prompt,
                    "images": [img_base64],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 40,
                    }
                },
                timeout=900
            )

            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
                return {"alert": False, "type": "NONE", "confidence": 0.0,
                        "description": "API error"}

            result_text = response.json().get("response", "").strip()
            logger.info(f"VLM raw response: {result_text}")

            # Parse JSON response
            return self._parse_response(result_text)

        except requests.exceptions.Timeout:
            logger.warning("VLM analysis timed out")
            return {"alert": False, "type": "NONE", "confidence": 0.0,
                    "description": "Analysis timed out"}
        except Exception as e:
            logger.error(f"VLM analysis error: {e}")
            return {"alert": False, "type": "NONE", "confidence": 0.0,
                    "description": f"Error: {str(e)}"}

    def _parse_response(self, text):
        """Parse VLM response, handling various formats."""
        description = text.strip()
        text_lower = description.lower()
        
        type_str = "NONE"
        is_alert = False
        
        # Check for hazard keywords directly mapped, using word boundaries to prevent partial matches like 'hit' in 'white'
        import re
        if re.search(r'\b(fire|flame|blazes?|burning building)\b', text_lower): 
            type_str = "FIRE"
            is_alert = True
        elif re.search(r'\b(smokes?)\b', text_lower): 
            type_str = "SMOKE"
            is_alert = True
        elif re.search(r'\b(weapon|gun|knife|pistol|rifle)\b', text_lower): 
            type_str = "WEAPON"
            is_alert = True
        elif re.search(r'\b(fight|fighting|violence|violent|punch|punching|kick|kicking|assault|hit|attacking|attack|beating|brawl|striking|choking|grabbing)\b', text_lower):
            type_str = "VIOLENCE"
            is_alert = True
        elif re.search(r'\b(fallen person|person on the ground|collapsed)\b', text_lower): 
            type_str = "FALLEN_PERSON"
            is_alert = True
        elif re.search(r'\b(intrud|break in|climbing over)\b', text_lower): 
            type_str = "INTRUSION"
            is_alert = True
            
        return {
            "alert": is_alert,
            "type": type_str,
            "confidence": 0.8 if is_alert else 0.0,
            "description": description[:200] if description else "Normal scene"
        }

    def is_available(self):
        """Check if VLM is available."""
        return self._available
