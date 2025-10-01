import os
import tempfile
from flask import Flask
import oci

app = Flask(__name__)

# Environment variables
OCI_USER = os.environ['OCI_USER']
OCI_TENANCY = os.environ['OCI_TENANCY']
OCI_FINGERPRINT = os.environ['OCI_FINGERPRINT']
OCI_PRIVATE_KEY_CONTENT = os.environ['OCI_PRIVATE_KEY']
OCI_REGION = os.environ['OCI_REGION']
SUBNET_ID = os.environ['SUBNET_ID']
SSH_PUBLIC_KEY = os.environ['SSH_PUBLIC_KEY']

# Image and Shape
IMAGE_ID = "ocid1.image.oc1.me-abudhabi-1.aaaaaaaaaqvmwhc37ngnjgdy4jyegnudltaqwdufutvxuzlrylphlqqfj6ya"  # Ubuntu 24.04 Minimal aarch64
SHAPE = "VM.Standard.A1.Flex"  # Always Free-eligible

# Write private key to a temp file for OCI SDK
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(OCI_PRIVATE_KEY_CONTENT.encode())
    PRIVATE_KEY_FILE = f.name

# OCI client
config = {
    "user": OCI_USER,
    "tenancy": OCI_TENANCY,
    "fingerprint": OCI_FINGERPRINT,
    "key_file": PRIVATE_KEY_FILE,
    "region": OCI_REGION
}

compute_client = oci.core.ComputeClient(config)

@app.route("/")
def create_instance():
    try:
        instance_name = "auto-instance"
        launch_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=OCI_TENANCY,
            display_name=instance_name,
            shape=SHAPE,
            image_id=IMAGE_ID,
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=SUBNET_ID,
                assign_public_ip=True
            ),
            metadata={
                "ssh_authorized_keys": SSH_PUBLIC_KEY
            }
        )

        response = compute_client.launch_instance(launch_details)
        instance_ocid = response.data.id
        return f"Başarılı! Instance OCID: {instance_ocid}"

    except Exception as e:
        return f"Hata oluştu: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
