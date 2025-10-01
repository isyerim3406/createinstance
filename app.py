import os
import time
import tempfile
from flask import Flask, jsonify
import oci

app = Flask(__name__)

# ENV değişkenleri
OCI_USER = os.environ.get("OCI_USER")
OCI_TENANCY = os.environ.get("OCI_TENANCY")
OCI_FINGERPRINT = os.environ.get("OCI_FINGERPRINT")
OCI_REGION = os.environ.get("OCI_REGION")
SUBNET_ID = os.environ.get("SUBNET_ID")
SSH_PUBLIC_KEY = os.environ.get("SSH_PUBLIC_KEY")
OCI_PRIVATE_KEY = os.environ.get("OCI_PRIVATE_KEY")  # temp dosya olarak kullanılacak

STATUS = {"last_attempt": None, "last_result": None, "message": None}

def create_temp_key_file(private_key_str):
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w")
    temp_file.write(private_key_str)
    temp_file.close()
    return temp_file.name

def attempt_instance_creation():
    global STATUS
    STATUS["last_attempt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Private key temp dosyası
        private_key_file = create_temp_key_file(OCI_PRIVATE_KEY)

        # Config
        config = {
            "user": OCI_USER,
            "tenancy": OCI_TENANCY,
            "fingerprint": OCI_FINGERPRINT,
            "region": OCI_REGION,
            "key_file": private_key_file,
        }

        compute_client = oci.core.ComputeClient(config)

        # Instance details
        instance_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=OCI_TENANCY,
            display_name="Render-Test-VM",
            shape="VM.Standard.A1.Flex",
            create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=SUBNET_ID),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id="ocid1.image.oc1.me-abudhabi-1.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # Canonical Ubuntu 24.04 Minimal aarch64
            ),
            metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY}
        )

        response = compute_client.launch_instance(instance_details)
        STATUS["last_result"] = "success"
        STATUS["message"] = f"Instance launched: {response.data.id}"

    except Exception as e:
        STATUS["last_result"] = "failure"
        STATUS["message"] = str(e)

    finally:
        if os.path.exists(private_key_file):
            os.remove(private_key_file)

# Background loop
def background_worker():
    while True:
        attempt_instance_creation()
        time.sleep(120)  # 2 dakika bekle, istersen arttırabilirsin

import threading
threading.Thread(target=background_worker, daemon=True).start()

@app.route("/")
def index():
    if STATUS["last_result"] == "success":
        return f"✅ OCI Instance Creator is running! Last instance: {STATUS['message']}"
    elif STATUS["last_result"] == "failure":
        return f"❌ Hata oluştu: {STATUS['message']}"
    else:
        return "⏳ Başlatılıyor..."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
