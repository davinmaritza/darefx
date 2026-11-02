import os

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("CONFIDENCE_THRESHOLD=0.52", "CONFIDENCE_THRESHOLD=0.40")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("CONFIDENCE_THRESHOLD updated to 0.40 in .env")
else:
    print(".env not found")
