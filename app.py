from flask import Flask, jsonify
import os
import threading
import time
# OCI SDK
import oci

app = Flask(__name__)

# Durum değişkeni
INSTANCE_CREATED = False

# /status endpoint
@app.route("/status")
def status():
    if INSTANCE_CREATED:
        return "✅ Instance başarıyla oluşturuldu"
    else:
        return "⏳ Instance henüz oluşturulmadı veya deneme devam ediyor"

# Arka planda instance oluşturma işlevi
def create_instance():
    global INSTANCE_CREATED
    try:
        config = {
            "user": os.environ["OCI_USER"],
            "key_file": "/tmp/oci_private_key.pem",
            "fingerprint": os.environ["OCI_FINGERPRINT"],
            "tenancy": os.environ["OCI_TENANCY"],
            "region": os.environ["OCI_REGION"]
        }

        # Private key temp dosyası
        with open(config["key_file"], "w") as f:
            f.write(os.environ["OCI_PRIVATE_KEY"])
        
        compute_client = oci.core.ComputeClient(config)
        
        launch_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=os.environ["OCI_TENANCY"],
            display_name="MyInstance",
            shape="VM.Standard.A1.Flex",
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id="ocid1.image.oc1.me-abudhabi-1.xxxxxxxx"
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ["SUBNET_ID"],
                assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": os.environ["SSH_PUBLIC_KEY"]}
        )

        response = compute_client.launch_instance(launch_details)
        if response.status == 200 or response.status == 201:
            INSTANCE_CREATED = True

    except Exception as e:
        print("Hata oluştu:", e)

# Uygulama başlarken thread ile çalıştır
threading.Thread(target=create_instance, daemon=True).start()

# Flask port ayarı
port = int(os.environ.get("PORT", 8080))
app.run(host="0.0.0.0", port=port)
