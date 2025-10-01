from flask import Flask
import os
import oci
import time

app = Flask(__name__)

# ================= ENV DEĞİŞKENLERİ =================
OCI_USER = os.environ.get("OCI_USER")
OCI_TENANCY = os.environ.get("OCI_TENANCY")
OCI_REGION = os.environ.get("OCI_REGION", "me-abudhabi-1")
OCI_FINGERPRINT = os.environ.get("OCI_FINGERPRINT")
OCI_PRIVATE_KEY_PATH = "/tmp/oci_api_key.pem"
SUBNET_ID = os.environ.get("SUBNET_ID")
SSH_PUBLIC_KEY = os.environ.get("SSH_PUBLIC_KEY")

# ================= PRIVATE KEY TEMP DOSYA =================
if not os.path.exists(OCI_PRIVATE_KEY_PATH):
    with open(OCI_PRIVATE_KEY_PATH, "w") as f:
        f.write(os.environ.get("OCI_PRIVATE_KEY", ""))
    os.chmod(OCI_PRIVATE_KEY_PATH, 0o600)

# ================= OCI CLIENT =================
config = {
    "user": OCI_USER,
    "tenancy": OCI_TENANCY,
    "region": OCI_REGION,
    "fingerprint": OCI_FINGERPRINT,
    "key_file": OCI_PRIVATE_KEY_PATH
}

compute_client = oci.core.ComputeClient(config)

# ================= INSTANCE DURUMU =================
instance_launched = False
instance_ocid = None

def launch_instance():
    global instance_launched, instance_ocid
    if instance_launched:
        return "Instance zaten oluşturuldu: " + instance_ocid

    try:
        instance_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=OCI_TENANCY,
            display_name="auto-instance",
            shape="VM.Standard.A1.Flex",
            subnet_id=SUBNET_ID,
            image_id="ocid1.image.oc1.me-abudhabi-1.aaaaaaaa3fnh62i7pklfip3yx2usxwjmurgj7g62zgpgmcfjg3vf6wu56eoq",  # Ubuntu 24.04 Minimal aarch64
            metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY}
        )
        response = compute_client.launch_instance(instance_details)
        instance_ocid = response.data.id
        instance_launched = True
        return f"✅ Instance oluşturuldu: {instance_ocid}"
    except oci.exceptions.ServiceError as e:
        return f"❌ Hata oluştu: {e}"

# ================= FLASK ROUTES =================
@app.route("/")
def home():
    return "OCI Instance Creator is running!"

@app.route("/status")
def status():
    return launch_instance()

# ================= MAIN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
