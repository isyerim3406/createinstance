import os
from flask import Flask, jsonify, request
import oci
import tempfile
import base64

app = Flask(__name__)

# --- SIGNER VE KONFİGÜRASYON FONKSİYONLARI ---

def get_signer():
    """Ortam değişkenlerinden OCI kimlik doğrulama yapılandırmasını oluşturur."""
    
    # Base64 veya ham anahtar içeriğini al
    if "OCI_PRIVATE_KEY_BASE64" in os.environ:
        private_key_encoded = os.environ["OCI_PRIVATE_KEY_BASE64"]
        # Base64'ten decode et (bu genellikle en güvenli yoldur)
        private_key = base64.b64decode(private_key_encoded).decode('utf-8')
    elif "OCI_PRIVATE_KEY" in os.environ:
        private_key = os.environ["OCI_PRIVATE_KEY"]
        if "\\n" in private_key:
            # AWK çıktısındaki çift ters eğik çizgiyi (\n) gerçek yeni satıra dönüştür
            private_key = private_key.replace("\\n", "\n")
    else:
        raise KeyError("OCI_PRIVATE_KEY or OCI_PRIVATE_KEY_BASE64 environment variable is missing.")
    
    # Geçici dosyaya yazma: UnicodeDecodeError'ı çözmek için güvenli mod kullanılır.
    # Ayrıca anahtarın etrafındaki tüm boşluklar temizlenir (.strip())
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pem', encoding='utf-8', newline=None) as key_file:
            key_file.write(private_key.strip()) 
            key_file_path = key_file.name
    except Exception as e:
        raise IOError(f"Error writing private key to temp file: {str(e)}")
    
    # Config dict oluştur (Tüm OCID'lerin temizlendiğinden emin olmak için .strip() kullanılır)
    config = {
        "tenancy": os.environ["OCI_TENANCY_OCID"].strip(),
        "user": os.environ["OCI_USER_OCID"].strip(),
        "fingerprint": os.environ["OCI_FINGERPRINT"].strip(),
        "key_file": key_file_path,
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1").strip()
    }
    
    return config

# --- ANA İŞLEVLER (COMPUTE İŞLEMLERİ) ---

def launch_instance():
    """OCI'da VM.Standard.A1.Flex (Ampere) instance başlatır."""
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        
        # Flex Shape yapılandırması: InvalidParameter/CannotParseRequest hatasını çözmek için
        # OCPUS ve MEMORY tam sayı (integer) olarak gönderilir.
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=1,
            memory_in_gbs=6
        )
        
        # Instance detayları: Tüm OCID'ler ve string'ler .strip() ile temizlenir.
        instance_details = oci.core.models.LaunchInstanceDetails(
            # OCI_AVAILABILITY_DOMAIN ortam değişkeninde TgOw:ME-ABUDHABI-1-AD-1 gibi
            # doğru alan adının ayarlı olduğundan emin olun.
            availability_domain=os.environ.get("OCI_AVAILABILITY_DOMAIN").strip(),
            
            compartment_id=os.environ["OCI_COMPARTMENT_OCID"].strip(),
            shape="VM.Standard.A1.Flex",
            shape_config=shape_config,
            
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=os.environ["OCI_IMAGE_ID"].strip()
            ),
            
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ["OCI_SUBNET_ID"].strip(),
                assign_public_ip=True
            ),
            
            display_name=os.environ.get("OCI_INSTANCE_NAME", "auto-instance").strip(),
            
            # OCI_SSH_PUBLIC_KEY'in OpenSSH formatında (ssh-rsa AAA...) ve temiz (.strip())
            # olduğundan emin olun.
            metadata={
                "ssh_authorized_keys": os.environ.get("OCI_SSH_PUBLIC_KEY", "").strip()
            } if os.environ.get("OCI_SSH_PUBLIC_KEY") else {}
        )
        
        response = compute_client.launch_instance(instance_details)
        
        return {
            "status": "success",
            "message": "Instance launch request sent successfully",
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
            "operation_name": "launch_instance",
            "details": str(e.details) if hasattr(e, 'details') else str(e)
        }
    except KeyError as e:
        return {
            "status": "error",
            "error_type": "Configuration Error",
            "message": f"Missing required environment variable: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }


def check_instance(instance_id):
    # ... (diğer fonksiyonlar, check_instance, stop_instance, vb. kodları burada devam eder)
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        response = compute_client.get_instance(instance_id)
        return {
            "status": "success",
            "instance_id": response.data.id,
            "lifecycle_state": response.data.lifecycle_state,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_instances():
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        compartment_id = os.environ["OCI_COMPARTMENT_OCID"].strip()
        instances = compute_client.list_instances(compartment_id=compartment_id)
        instance_list = [{
            "id": inst.id,
            "display_name": inst.display_name,
            "lifecycle_state": inst.lifecycle_state,
            "shape": inst.shape
        } for inst in instances.data]
        return {"status": "success", "count": len(instance_list), "instances": instance_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def instance_action(instance_id, action):
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        compute_client.instance_action(instance_id, action.upper())
        return {"status": "success", "message": f"Instance {instance_id} {action.lower()}ing..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- FLASK YOLLARI (ROUTES) ---

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/")
def home():
    result = launch_instance()
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

@app.route("/debug/config")
def debug_config():
    """Environment variable'ları kontrol et (güvenli)"""
    config = {
        "tenancy": os.environ.get("OCI_TENANCY_OCID", "NOT_SET")[:20] + "...",
        "user": os.environ.get("OCI_USER_OCID", "NOT_SET")[:20] + "...",
        "fingerprint": os.environ.get("OCI_FINGERPRINT", "NOT_SET"),
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1"),
        "private_key_length": len(os.environ.get("OCI_PRIVATE_KEY", "")),
        "private_key_starts_with": os.environ.get("OCI_PRIVATE_KEY", "")[:30],
        "compartment": os.environ.get("OCI_COMPARTMENT_OCID", "NOT_SET")[:20] + "...",
        "ad": os.environ.get("OCI_AVAILABILITY_DOMAIN", "NOT_SET"),
    }
    return jsonify(config), 200

@app.route("/debug/auth")
def debug_auth():
    """OCI authentication'ı test et"""
    try:
        config = get_signer()
        identity_client = oci.identity.IdentityClient(config)
        user = identity_client.get_user(os.environ["OCI_USER_OCID"].strip())
        
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
        }), 400

@app.route("/check/<instance_id>")
def get_instance_status(instance_id):
    result = check_instance(instance_id)
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

@app.route("/list")
def get_list_instances():
    result = list_instances()
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

@app.route("/stop/<instance_id>")
def stop_instance_route(instance_id):
    result = instance_action(instance_id, "STOP")
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

@app.route("/start/<instance_id>")
def start_instance_route(instance_id):
    result = instance_action(instance_id, "START")
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

@app.route("/terminate/<instance_id>")
def terminate_instance_route(instance_id):
    result = instance_action(instance_id, "TERMINATE")
    return (jsonify(result), 200) if result["status"] == "success" else (jsonify(result), 400)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
