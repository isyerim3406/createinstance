import os
import time
import oci
from flask import Flask

app = Flask(__name__)

# Signer fonksiyonu: Private key'i string olarak alıyoruz
def get_signer():
    private_key = oci.signer.load_private_key_from_string(
        os.environ["OCI_PRIVATE_KEY"],
        None  # passphrase yok
    )
    return oci.signer.Signer(
        tenancy=os.environ["OCI_TENANCY_OCID"],
        user=os.environ["OCI_USER_OCID"],
        fingerprint=os.environ["OCI_FINGERPRINT"],
        private_key=private_key
    )

# Instance başlatma fonksiyonu
def launch_instance():
    compute_client = oci.core.ComputeClient(config={}, signer=get_signer())

    instance_details = oci.core.models.LaunchInstanceDetails(
        availability_domain="Uocm:ME-ABUDHABI-1-AD-1",  # Default AD, bölgeye göre gerekirse değiştir
        compartment_id=os.environ["OCI_COMPARTMENT_OCID"],
        shape="VM.Standard.A1.Flex",
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            source_type="image",
            image_id=os.environ["OCI_IMAGE_ID"]
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=os.environ["OCI_SUBNET_ID"],
            assign_public_ip=True
        ),
        display_name="auto-instance"
    )

    try:
        response = compute_client.launch_instance(instance_details)
        return f"Success! Instance launched: {response.data.id}"
    except Exception as e:
        return f"Failed: {str(e)}"

@app.route("/")
def home():
    # Her girişte otomatik deneme
    result = launch_instance()
    return result

if __name__ == "__main__":
    # Render otomatik başlatırken hata almasın diye loop yerine direkt Flask server çalışıyor
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
