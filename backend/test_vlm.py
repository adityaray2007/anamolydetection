import sys
import unittest
import numpy as np
import time

from core.vlm_engine import VLMEngine

engine = VLMEngine()
print("1. Initializing VLM Engine...")
engine.initialize()

print(f"Engine available: {engine.is_available()}")

print("2. Generating dummy frame...")
frame = np.zeros((480, 640, 3), dtype=np.uint8)

print("3. Analyzing frame...")
start_time = time.time()
result = engine.analyze_frame(frame)
end_time = time.time()

print(f"Analysis completed in {end_time - start_time:.2f} seconds.")
print("Result:", result)
