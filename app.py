import os
import tempfile
import base64
from flask import Flask, jsonify
import oci

app = Flask(__name__)

# -----------------------------
# Signer ve Config Fonksiyonu
# -----------------------------
def get_signer():
    # Base64 encoded private key'i decode et
    if "OCI_PRIVATE_KEY_BASE64" in os.environ:
        private_key = base64.b64decode(os.environ["OCI_PRIVATE_KEY_BASE64"]).decode("utf-8")
    else:
        raise KeyError("OCI_PRIVATE_KEY_BASE64 environment variable missing")

    # Geçici dosya oluştur
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".pem") as key_file:
        key_file.write(private_key)
        key_file_path = key_file.name

    config = {
        "tenancy": os.environ["OCI_TENANCY_OCID"],
        "user": os.environ["OCI_USER_OCID"],
        "fingerprint": os.environ["OCI_FINGERPRINT"],
        "key_file": key_file_path,
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1")
    }

    return config

# -----------------------------
# Debug Endpoint
# -----------------------------
@app.route("/debug/config")
def debug_config():
    try:
        config = get_signer()
        return jsonify({
            "tenancy": config["tenancy"][:20] + "...",
            "user": config["user"][:20] + "...",
            "fingerprint": config["fingerprint"],
            "region": config["region"]
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/debug/auth")
def debug_auth():
    try:
        config = get_signer()
        identity_client = oci.identity.IdentityClient(config)
        user = identity_client.get_user(config["user"])
        return jsonify({
            "status": "success",
            "user_name": user.data.name,
            "user_id": user.data.id
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------
# Instance Fonksiyonları
# -----------------------------
def launch_instance():
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)

        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=1.0,
            memory_in_gbs=6.0
        )

        instance_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=os.environ.get("OCI_AVAILABILITY_DOMAIN"),
            compartment_id=os.environ["OCI_COMPARTMENT_OCID"],
            shape="VM.Standard.A1.Flex",
            shape_config=shape_config,
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=os.environ["OCI_IMAGE_ID"]
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ["OCI_SUBNET_ID"],
                assign_public_ip=True
            ),
            display_name=os.environ.get("OCI_INSTANCE_NAME", "auto-instance"),
            metadata={
                "ssh_authorized_keys": os.environ.get("OCI_SSH_PUBLIC_KEY", "")
            }
        )

        response = compute_client.launch_instance(instance_details)

        return {
            "status": "success",
            "instance_id": response.data.id,
            "display_name": response.data.display_name,
            "lifecycle_state": response.data.lifecycle_state
        }

    except oci.exceptions.ServiceError as e:
        return {"status": "error", "code": e.code, "message": e.message, "details": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Sağlık Kontrolü
@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# Ana Endpoint
@app.route("/")
def home():
    result = launch_instance()
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
