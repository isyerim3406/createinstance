import os
from flask import Flask, jsonify, request
import oci

app = Flask(__name__)

# Debug endpoint - Config'i test et
@app.route("/debug/config")
def debug_config():
    """Environment variable'ları kontrol et (güvenli)"""
    try:
        config = {
            "tenancy": os.environ.get("OCI_TENANCY_OCID", "NOT_SET")[:20] + "...",
            "user": os.environ.get("OCI_USER_OCID", "NOT_SET")[:20] + "...",
            "fingerprint": os.environ.get("OCI_FINGERPRINT", "NOT_SET"),
            "region": os.environ.get("OCI_REGION", "me-abudhabi-1"),
            "private_key_length": len(os.environ.get("OCI_PRIVATE_KEY", "")),
            "private_key_starts_with": os.environ.get("OCI_PRIVATE_KEY", "")[:30],
            "compartment": os.environ.get("OCI_COMPARTMENT_OCID", "NOT_SET")[:20] + "..."
        }
        return jsonify(config), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Auth test endpoint
@app.route("/debug/auth")
def debug_auth():
    """OCI authentication'ı test et"""
    try:
        config = get_signer()
        
        # Identity client ile basit bir test
        identity_client = oci.identity.IdentityClient(config)
        user = identity_client.get_user(os.environ["OCI_USER_OCID"])
        
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "user_name": user.data.name,
            "user_id": user.data.id
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }), 500

# Signer fonksiyonu - BASE64 ile
def get_signer():
    import tempfile
    import base64
    
    # Base64 encoded private key'i decode et veya direkt kullan
    if "OCI_PRIVATE_KEY_BASE64" in os.environ:
        private_key_encoded = os.environ["OCI_PRIVATE_KEY_BASE64"]
        private_key = base64.b64decode(private_key_encoded).decode('utf-8')
    elif "OCI_PRIVATE_KEY" in os.environ:
        private_key = os.environ["OCI_PRIVATE_KEY"]
        if "\\n" in private_key:
            # AWK çıktısındaki çift ters eğik çizgiyi (\n) gerçek yeni satıra dönüştür
            private_key = private_key.replace("\\n", "\n")
    else:
        raise KeyError("OCI_PRIVATE_KEY or OCI_PRIVATE_KEY_BASE64")
    
    # Geçici dosyaya yazma kısmındaki UnicodeDecodeError hatası çözümü:
    # 'w+' modu ve 'utf-8' encoding kullanılarak metin yazma garantilenir.
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pem', encoding='utf-8', newline=None) as key_file:
        key_file.write(private_key.strip()) 
        key_file_path = key_file.name
    
    # Config dict oluştur
    config = {
        "tenancy": os.environ["OCI_TENANCY_OCID"],
        "user": os.environ["OCI_USER_OCID"],
        "fingerprint": os.environ["OCI_FINGERPRINT"],
        "key_file": key_file_path,
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1")
    }
    
    return config

# Instance başlatma fonksiyonu
def launch_instance():
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=1.0,
            memory_in_gbs=6.0
        )

        instance_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=os.environ.get("OCI_AVAILABILITY_DOMAIN", "Uocm:ME-ABUDHABI-1-AD-1"),
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
            } if os.environ.get("OCI_SSH_PUBLIC_KEY") else {}
        )
        
        response = compute_client.launch_instance(instance_details)
        
        return {
            "status": "success",
            "message": "Instance launched successfully",
            "instance_id": response.data.id,
            "display_name": response.data.display_name,
            "lifecycle_state": response.data.lifecycle_state
        }

    except oci.exceptions.ServiceError as e:
        return {
            "status": "error",
            "error_type": "OCI Service Error",
            "code": e.code,
            "message": e.message,
            "details": str(e)
        }
    except KeyError as e:
        return {
            "status": "error",
            "error_type": "Configuration Error",
            "message": f"Missing environment variable: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }

# Sağlık kontrolü
@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# Ana endpoint
@app.route("/")
def home():
    result = launch_instance()
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 500)

# Instance durumunu kontrol
@app.route("/check/<instance_id>")
def check_instance(instance_id):
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        response = compute_client.get_instance(instance_id)
        return jsonify({
            "status": "success",
            "instance_id": response.data.id,
            "display_name": response.data.display_name,
            "lifecycle_state": response.data.lifecycle_state,
            "availability_domain": response.data.availability_domain,
            "time_created": str(response.data.time_created)
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Tüm instance'ları listele
@app.route("/list")
def list_instances():
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        instances = compute_client.list_instances(compartment_id=os.environ["OCI_COMPARTMENT_OCID"])
        instance_list = [{
            "id": inst.id,
            "display_name": inst.display_name,
            "lifecycle_state": inst.lifecycle_state,
            "shape": inst.shape
        } for inst in instances.data]
        return jsonify({"status": "success", "count": len(instance_list), "instances": instance_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Instance durdur
@app.route("/stop/<instance_id>")
def stop_instance(instance_id):
    try:
        signer = get_signer()
        # OCI istemcileri config dict'i veya signer alabilir. Burada signer kullanıldı.
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        compute_client.instance_action(instance_id, "STOP")
        return jsonify({"status": "success", "message": f"Instance {instance_id} stopping..."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Instance başlat
@app.route("/start/<instance_id>")
def start_instance(instance_id):
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        compute_client.instance_action(instance_id, "START")
        return jsonify({"status": "success", "message": f"Instance {instance_id} starting..."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Instance sil
@app.route("/terminate/<instance_id>")
def terminate_instance(instance_id):
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        compute_client.terminate_instance(instance_id)
        return jsonify({"status": "success", "message": f"Instance {instance_id} terminating..."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
