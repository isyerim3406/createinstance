import os
import time
from flask import Flask
import oci

app = Flask(__name__)

def get_signer():
    private_key = os.environ["OCI_PRIVATE_KEY"].replace("\\n", "\n")
    return oci.signer.Signer(
        tenancy=os.environ["OCI_TENANCY_OCID"],
        user=os.environ["OCI_USER_OCID"],
        fingerprint=os.environ["OCI_FINGERPRINT"],
        private_key_content=private_key,
        pass_phrase=None
    )

def launch_instance():
    compute_client = oci.core.ComputeClient(config={}, signer=get_signer())
    try:
        response = compute_client.launch_instance(
            oci.core.models.LaunchInstanceDetails(
                compartment_id=os.environ["OCI_COMPARTMENT_OCID"],
                availability_domain="Uocm:ME-ABUDHABI-1-AD-1",
                shape="VM.Standard.A1.Flex",
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=1,
                    memory_in_gbs=6
                ),
                display_name="auto-instance",
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    source_type="image",
                    image_id=os.environ["OCI_IMAGE_ID"]
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=os.environ["OCI_SUBNET_ID"],
                    assign_public_ip=True
                )
            )
        )
        return f"✅ Başarılı: Instance başlatıldı - {response.data.id}"
    except Exception as e:
        return f"❌ Hata oluştu: {str(e)}"

@app.route("/")
def index():
    result = launch_instance()
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # 2 dakikada bir tekrar denemek için
    while True:
        print(launch_instance())
        time.sleep(120)  # 120 saniye = 2 dk
    app.run(host="0.0.0.0", port=port)
