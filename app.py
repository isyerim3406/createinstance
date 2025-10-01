from flask import Flask
import os
import tempfile
import oci
import time

app = Flask(__name__)

# --- ENV VARS ---
OCI_USER = os.getenv("OCI_USER")
OCI_TENANCY = os.getenv("OCI_TENANCY")
OCI_FINGERPRINT = os.getenv("OCI_FINGERPRINT")
OCI_PRIVATE_KEY_CONTENT = os.getenv("OCI_PRIVATE_KEY")
OCI_REGION = os.getenv("OCI_REGION")
SUBNET_ID = os.getenv("SUBNET_ID")
SSH_PUBLIC_KEY = os.getenv("SSH_PUBLIC_KEY")

# --- Write private key to temp file ---
temp_key_file = tempfile.NamedTemporaryFile(delete=False)
temp_key_file.write(OCI_PRIVATE_KEY_CONTENT.encode())
temp_key_file.close()
PRIVATE_KEY_PATH = temp_key_file.name

# --- OCI Config ---
config = {
    "user": OCI_USER,
    "tenancy": OCI_TENANCY,
    "fingerprint": OCI_FINGERPRINT,
    "key_file": PRIVATE_KEY_PATH,
    "region": OCI_REGION
}

compute_client = oci.core.ComputeClient(config)

# --- VM parameters ---
INSTANCE_DISPLAY_NAME = "Render-Auto-Instance"
AVAIL_DOMAIN = None  # Optional: leave None for auto
IMAGE_ID = "ocid1.image.oc1.me-abudhabi-1.amaaaaaabqku7jqag7lrxakpxhcxobmaljwpgkbygtpv5lk6qv5hdcavtnqa"  # Canonical Ubuntu 24.04 Minimal aarch64
SHAPE = "VM.Standard.A1.Flex"
WAIT_INTERVAL = 10  # seconds between retries

instance_created = False

def create_instance():
    global instance_created
    try:
        launch_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=OCI_TENANCY,
            display_name=INSTANCE_DISPLAY_NAME,
            shape=SHAPE,
            availability_domain=AVAIL_DOMAIN,
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=SUBNET_ID,
                assign_public_ip=True
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=IMAGE_ID
            ),
            metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY}
        )
        response = compute_client.launch_instance(launch_details)
        instance_created = True
        return f"Instance creation succeeded! OCID: {response.data.id}"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/")
def index():
    if instance_created:
        return "<h2>✅ Instance başarıyla oluşturuldu!</h2>"
    else:
        msg = create_instance()
        return f"<h2>Durum: {msg}</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080")))
