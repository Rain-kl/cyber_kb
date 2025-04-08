# app/config.py
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Tika 服务器配置
TIKA_SERVER_URL = os.environ.get("TIKA_SERVER_URL", "http://your-server-ip:9998")

# Ollama API 配置
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://your-ollama-server:11434")
OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL_NAME", "bge-m3")