import os
import tempfile
from flask import Flask
from dotenv import load_dotenv
import oci

# Load .env
load_dotenv()

app = Flask(__name__)

# Private key’i temp dosyaya yaz
private_key_content = os.getenv("OCI_PRIVATE_KEY")
with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
    f.write(private_key_content)
    key_file_path = f.name

# Oracle SDK config
config = {
    "user": os.getenv("OCI_USER"),
    "fingerprint": os.getenv("OCI_FINGERPRINT"),
    "tenancy": os.getenv("OCI_TENANCY"),
    "region": os.getenv("OCI_REGION"),
    "key_file": key_file_path
}

@app.route("/")
def home():
    return "OCI instance ile web servisi çalışıyor!"

if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", 8080))
    app.run(host="0.0.0.0", port=port)
