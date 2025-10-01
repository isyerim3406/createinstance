import os
from flask import Flask
from dotenv import load_dotenv
import oci

# Load .env
load_dotenv()

app = Flask(__name__)

# Oracle SDK için env değişkenlerini kullan
config = {
    "user": os.getenv("OCI_USER"),
    "fingerprint": os.getenv("OCI_FINGERPRINT"),
    "tenancy": os.getenv("OCI_TENANCY"),
    "region": os.getenv("OCI_REGION"),
    "key_file": os.getenv("OCI_PRIVATE_KEY_PATH", "oci_api_key.pem")
}

@app.route("/")
def home():
    return "OCI instance ile web servisi çalışıyor!"

if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", 8080))
    app.run(host="0.0.0.0", port=port)
