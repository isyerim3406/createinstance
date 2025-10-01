from flask import Flask, jsonify
import os
import oci
import tempfile

app = Flask(__name__)

# Basit test endpoint
@app.route("/")
def home():
    return "OCI Instance Creator is running!"

@app.route("/status")
def status():
    return jsonify({"status": "ready"})


# OCI Client ayarları environment variable'dan alınır
OCI_USER = os.environ.get("OCI_USER")
OCI_TENANCY = os.environ.get("OCI_TENANCY")
OCI_FINGERPRINT = os.environ.get("OCI_FINGERPRINT")
OCI_REGION = os.environ.get("OCI_REGION")
SUBNET_ID = os.environ.get("SUBNET_ID")
OCI_PRIVATE_KEY_CONTENT = os.environ.get("OCI_PRIVATE_KEY")

# Private key geçici dosya olarak yazılıyor
with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
    f.write(OCI_PRIVATE_KEY_CONTENT)
    PRIVATE_KEY_PATH = f.name

# OCI config
config = {
    "user": OCI_USER,
    "fingerprint": OCI_FINGERPRINT,
    "tenancy": OCI_TENANCY,
    "region": OCI_REGION,
    "key_file": PRIVATE_KEY_PATH
}

compute_client = oci.core.ComputeClient(config)

# Örnek: Instance oluşturma fonksiyonu (sadece deneme için)
def launch_instance():
    # Buraya güncel Image OCID ve Shape yazılacak
    image_id = "ocid1.image.oc1.me-abudhabi-1.aaaaaaaaaaaexample"
    shape = "VM.Standard.A1.Flex"
    display_name = "render-auto-instance"

    instance_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=OCI_TENANCY,
        display_name=display_name,
        shape=shape,
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=image_id
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID
        )
    )

    try:
        response = compute_client.launch_instance(instance_details)
        return {"status": "launched", "instance_id": response.data.id}
    except oci.exceptions.ServiceError as e:
        return {"status": "error", "message": str(e)}

@app.route("/launch")
def launch():
    result = launch_instance()
    return jsonify(result)


# Render port binding
port = int(os.environ.get("PORT", 8080))
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
